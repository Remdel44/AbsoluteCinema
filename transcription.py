import whisper, re, subprocess, os, time, torch

GT_SUBS_PATH_RAW = "ground_truth_subs/raw/"
GT_SUBS_PATH_CLEAN = "ground_truth_subs/cleaned/"

MOVIES_PATH= "../films/"  #Hors du git car trop volumineux
AUDIO_PATH = "input_audios/"
TRANSCRIPTS_PATH = "transcripted_subs/"

# 1. Ground truth: Extraction et nettoyage des dialogues à partir d'un fichier SRT
def dialogue_clean(file_path):
    """
    Extrait et nettoie les lines de dialogue d'un fichier de sous-titres (type SRT) 
    en supprimant les balises HTML/XML, les timestamps et les numéros de séquence.

    Args:
        file_path: Chemin vers le fichier SRT.

    Returns:
        list: Une liste contenant uniquement les dialogues nettoyés.
    """
    dialogues = []
    
    # Regex : supprimer les balises HTML/XML , les timestamps (-->) et les numéros de séquence (^d+$)
    regex_clean = re.compile(r'<\/?\w+.*?>|\d{1,2}:\d{2}:\d{2},\d{3} --> \d{1,2}:\d{2}:\d{2},\d{3}|^\d+$', re.IGNORECASE)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Erreur : Fichier '{file_path}' introuvable.")
        return []
    
    for line in lines:
        line = line.strip() 

        # Filtrer les lignes qui ne sont ni des numéros de séquence ni des marqueurs de temps
        if line and not re.match(r'^\d+$', line) and '-->' not in line:
            # Retirer les balises
            dialogue_nettoye = regex_clean.sub('', line)
            
            # Ajouter à la liste si il reste du texte
            if dialogue_nettoye.strip():
                dialogues.append(dialogue_nettoye.strip())

    #Save dialogues vers fichier txt
    dialogues_txt_path = GT_SUBS_PATH_CLEAN + TEST_MOVIE + ".srt"
    with open(dialogues_txt_path, 'w', encoding='utf-8') as f:
        for dialogue in dialogues:
            f.write(dialogue + '\n')
    
    return dialogues

TEST_MOVIE = "Kill_Bill_Volume_2"
gt_subs_clean = dialogue_clean(f"{GT_SUBS_PATH_RAW}{TEST_MOVIE}_raw.srt")
# print("Dialogues extraits:\n", gt_subs_clean[:20])





## ----------------------------------------------------------------------------------------------------------------------------------------------------

#2. Transcription par Whisper

## 2.1: Extraction de l'audio anglais d'un film .mkv
def extract_eng_track(video_path, audio_dir="input_audios"):
    """
    Extrait le premier flux audio en anglais d'un fichier vidéo et le copie dans le dossier spécifié.

    Args:
        video_path : Chemin vers le fichier vidéo (ex: 'Kill_Bill_Volume_2.mkv').
        audio_dir : Dossier de sauvegarde du fichier audio.
    
    Returns:
        str: Le chemin du fichier audio créé.
    """

    #Vérifier existence du fichier d'entrée
    if not os.path.isfile(video_path):
        print(f"Erreur : Fichier vidéo '{video_path}' introuvable.")
        exit()

    # Identifier index du flux audio anglais
    try:
        # ffprobe pour obtenir les informations des streams audio et de langue
        ffprobe_cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-hide_banner',
            '-select_streams', 'a', 
            '-show_entries', 'stream=index,codec_name:stream_tags=language', 
            '-of', 'json', # Format de sortie JSON pour parser ensuite
            video_path
        ]
        # Subprocess pour exécuter la commande et capturer la sortie
        print(video_path)
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        streams_data = result.stdout

    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de ffprobe : {e}")
        exit()
    
    # Parcourir les résultats JSON pour trouver le premier index 'eng'
    index_anglais = None
    codec_audio = None
    
    # Parsing des données pour trouver l'index de l'audio anglais et le codec
    for line in streams_data.split('\n'):
        if '"tag_string": "eng"' in line or '"language": "eng"' in line:
             # Chercher l'index qui précède
            match_index = re.search(r'"index": (\d+)', streams_data)
            if match_index:
                index_anglais = match_index.group(1)
            
            # Chercher le codec pour l'extension
            match_codec = re.search(r'"codec_name": "(\w+)"', streams_data)
            if match_codec:
                 codec_audio = match_codec.group(1).lower()

            if index_anglais and codec_audio:
                break # On prend le premier trouvé

    if not index_anglais:
        print("Aucun flux audio en anglais trouvé.")
        exit()

    # Déterminer l'extension du fichier de sortie (pour une copie efficace)
    # Les formats courants sont aac, ac3, dts. Sinon, on force le MP3 pour la compatibilité.
    extension = 'aac' if codec_audio =='aac' else 'ac3' if codec_audio == 'ac3' else None

    # Créer le chemin du fichier de sortie
    nom_base = os.path.splitext(os.path.basename(video_path))[0]
    audio_out_path = os.path.join(audio_dir, f"{nom_base}_eng.{extension}")
    
    # Supprimer fichier de sortie s'il existe déjà
    if os.path.isfile(audio_out_path): os.remove(audio_out_path)

    # ffmpeg pour extraire le flux audio anglais
    if extension in ['aac', 'ac3']:
        ffmpeg_cmd = [
            'ffmpeg', 
            '-i', video_path, 
            '-v', 'error',
            '-hide_banner',
            '-map', f'0:{index_anglais}',
            '-vn',                       # Ignorer la vidéo
            '-c:a', 'copy',              # Copie le flux audio
            audio_out_path
        ]
        print(f"Copie du flux audio {index_anglais}, codec: ({codec_audio})")
    else:
        print('Flux audio non compatible détecté.(AAC/AC3 nécessaire)')
        exit()

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"\nAudio anglais extrait vers '{audio_out_path}'")
        return audio_out_path.replace('\\', '/')
    except subprocess.CalledProcessError as e:
        print(f"\nErreur lors de l'extraction FFmpeg : {e}")
        exit()


#2.2: Transcription audio avec Whisper
# Obtenir la durée totale, utile pour voir l'avancée de la fonction whisper_transcript sur un long fichier ---
def get_audio_duration(chemin_audio):
    """
    Encore ffprobe pour obtenir la durée du fichier.
    """
    try:
        # Commande ffprobe pour obtenir la durée en secondes
        cmd = [
            'ffprobe', 
            '-v', 'error',
            '-hide_banner', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            chemin_audio
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Erreur lors de la récupération de la durée audio : {e}")
        return 0.0

def whisper_transcript(input_audio, audio_duration):
    """
    Transcrit un fichier audio et affiche la progression, et sauvegarde en .txt

    Args:
        input_audio: Chemin vers le fichier audio.
        total_duration_seconds: Durée totale du fichier audio en secondes.
    
    Returns:
        str: Le texte complet
    """
    # Faire tourner whisper sur GPU car c'est long..
    if torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
 
    print("Whisper will run on: ", device)
    # Modèle turbo: Bon pour transcription anglais-anglais
    model = whisper.load_model("turbo", device=device)
    
    # Démarrer le chronomètre pour le temps réel
    start_time = time.time()
    
    print("\nDébut de la transcription. Durée totale de l'audio: ", time.strftime('%H:%M:%S', time.gmtime(audio_duration)))
    
    # Split l'audio en segments de 5 minutes (300s) pour pouvoir cancel sans faire une heure de transcription
    split_duration = 300
    output_splits_path = AUDIO_PATH + TEST_MOVIE + "/"

    print("\nDécoupage de l'audio en segments de", split_duration, "secondes...")

    # Créer le dossier de splits s'il n'existe pas
    os.makedirs(output_splits_path, exist_ok=True)
    try:
        split_cmd = [
                'ffmpeg', 
                '-i', input_audio,
                '-f', 'segment',
                '-segment_time', str(split_duration),
                '-c', 'copy',
                output_splits_path + "audio_split_%03d.ac3"
            ]
        result = subprocess.run(split_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du découpage de l'audio : {e}")
        return None
    dialogues = []
    # Transcription avec verbose=True pour suivre la progression
    for idx, audio_split in enumerate(os.listdir(output_splits_path)):
        print("Transcription du segment :", audio_split)
        split_dialogue = transcript_audio_split(model, output_splits_path + audio_split, idx)
        dialogues.append(split_dialogue)
    dialogues = '\n'.join(dialogues)

    # Exécution réussie -> Supprimer les splits temporaires
    for audio_split in os.listdir(output_splits_path):
        os.remove(output_splits_path + audio_split)

    # Afficher le temps écoulé
    temps_final_str = time.strftime('%H:%M:%S', time.gmtime(audio_duration))
    duration = time.time() - start_time
    print(f"Transcription terminée (Audio total : {temps_final_str}). Temps écoulé : {time.strftime('%H:%M:%S', time.gmtime(duration))}")

    ## Sauvegarde des dialogues avec timecodes vers fichier txt

    #Chemin du fichier de sortie
    dialogues_txt_path = TRANSCRIPTS_PATH + TEST_MOVIE + ".txt"
   
    with open(dialogues_txt_path, 'w', encoding='utf-8') as f:
        f.write(dialogues)

    return dialogues

    
def transcript_audio_split(model, split_path, idx):
    """
    Transcrit un segment audio et retourne le texte.

    Args:
        model: Modèle Whisper chargé
        split_path: Chemin vers le segment audio.
    
    Returns:
        str: Transcription du split audio.
    """
    
    try:
        print(f"\nTranscription du segment : {split_path}")
        result = model.transcribe(str(split_path), fp16=False, verbose=True )
        dialogues = result["text"]
        
        #Save dans un .txt temporaire au cas où

        temp_txt_path = 'transcripted_subs' + TEST_MOVIE + f'/audio_split_{idx}.txt'
        with open(temp_txt_path, 'w', encoding='utf-8') as f:
            f.write(dialogues)
        print(f"Transcription du segment sauvegardée vers '{temp_txt_path}'")
        return dialogues

    except Exception as e:
        print(f"Erreur lors de la transcription du segment {split_path}: \n{e}")
        return None




# Test
film_full_path = MOVIES_PATH+TEST_MOVIE+".mkv" 
test_audio_path = extract_eng_track(film_full_path)
audio_duration = get_audio_duration(test_audio_path)

transcription = whisper_transcript(test_audio_path, audio_duration)
if transcription:
    print("\n--- Transcription Finale (500 premiers caractères) ---")
    print(transcription[:500])


















# # Whisper coupe les audios longs en segments de 30s.
# def transcript_audio(input_audio):
#     # Whisper-turbo: transcription english-to-english 
#     model = whisper.load_model("turbo")
#     result = model.transcribe(str(input_audio), fp16=False)
#     return result["text"]

# # print(transcript_audio("combined.wav"))

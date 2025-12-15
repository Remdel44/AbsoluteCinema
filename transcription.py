import whisper, re, subprocess, os, time, torch, sys
from whisper.utils import format_timestamp # Fonction de formatage des timestamps

GT_SUBS_PATH = "ground_truth_subs/"
# GT_SUBS_PATH_RAW = "ground_truth_subs/raw/"
# GT_SUBS_PATH_CLEAN = "ground_truth_subs/cleaned/"

MOVIES_PATH= "../films/"  #Hors du git car trop volumineux
AUDIOS_PATH = "input_audios/"
TRANSCRIPTS_PATH = "transcripted_subs/"

## ----------------------------------------------------------------------------------------------------------------------------------------------------

# 1. Extraction de la liste de films
def get_movie_list(movies_dir=MOVIES_PATH):
    """
    Récupère la liste des films (sans extension) dans le dossier spécifié.

    Args:
        movies_dir: Dossier contenant les films.

    Returns:
        list: Liste des noms de films sans extension.
    """
    movie_paths = []
    movie_names = []
    print("Recherche des films dans: ", movies_dir)

    for file in os.listdir(movies_dir):
        if file.endswith(".mkv"):
            movie_paths.append(os.path.join(movies_dir, file))
            movie_file = os.path.split(file)[1]
            movie_name = movie_file.replace(' ', '_') # Retirer extension / remplacer espaces
            print("movie: ", movie_name)
            movie_names.append(movie_name)


    return movie_paths, movie_names

## ----------------------------------------------------------------------------------------------------------------------------------------------------

# 2. Ground truth: Extraction des dialogues sous format .srt
def extract_dialogues(movie_path, movie_name):
    """
    Extrait un fichier de sous-titres intégré d'un film .mkv et le sauvegarde en .srt.
    Args:
        movie_path: Chemin vers le fichier vidéo
        movie_name: Nom du film (sans extension)
    Returns:
        str: Chemin vers le fichier de sous-titres extrait.
    """

    print(f"Extraction des sous-titres: {movie_name}")
    #Vérifier existence du fichier mkv
    if not os.path.isfile(movie_path):
        print(f"Erreur extract_dialogues() : Fichier vidéo '{movie_path}' introuvable.")
        exit()

    # Chemin du fichier de sortie
    subs_out_path = os.path.join(GT_SUBS_PATH, f"{movie_name}.srt")

    # Sortie de fonction s'il existe déjà
    if os.path.isfile(subs_out_path): return subs_out_path.replace('\\', '/')


    try:
        #Trouver index sous-titre anglais
        ffprobe_index_cmd = ['ffprobe', '-i', movie_path, '-hide_banner']
        probe = subprocess.run(ffprobe_index_cmd, text=True, check=True, shell=True, capture_output=True)

        output = probe.stdout + probe.stderr # Combiner les deux sorties car ffprobe peut écrire dans stderr ?
        regex = re.compile(r"Stream #0:(\d+)\((eng|en)\): Subtitle:", re.IGNORECASE)
        match = regex.search(output)
        if match: sub_index = match.group(1) #Récupère l'index avec le regex
 
    except subprocess.CalledProcessError as e:
        print(f"\nErreur lors de l'extraction des sous-titres FFprobe : {e}")


    # ffmpeg pour extraire les sous-titres
    ffmpeg_sub = [
        'ffmpeg', 
        '-i', movie_path, 
        '-v', 'error',
        '-hide_banner',
        '-map', f'0:{sub_index}',  # Sélectionner le flux de sous-titres en anglais (s:m:language:eng)
        '-c:s', 'srt',                  # Sortie en format SRT
        subs_out_path
    ]

    try:
        subprocess.run(ffmpeg_sub, check=True)
        print(f"\nSous-titres extraits vers '{subs_out_path}'")
        return subs_out_path.replace('\\', '/')
    except subprocess.CalledProcessError as e:
        print(f"\nErreur lors de l'extraction des sous-titres FFmpeg : {e}")
        exit()





# (old) 2. Ground truth: Extraction et nettoyage des dialogues à partir d'un fichier SRT
def dialogue_clean(file_path):
    """
    Extrait et nettoie les lines de dialogue d'un fichier de sous-titres (type SRT) 
    en supprimant les balises HTML/XML, les timestamps et les numéros de séquence.

    Args:
        file_path: Chemin vers le fichier SRT.

    Returns:
        list: Une liste contenant uniquement les dialogues nettoyés.
    """
    # dialogues = []
    
    # # Regex : supprimer les balises HTML/XML , les timestamps (-->) et les numéros de séquence (^d+$)
    # regex_clean = re.compile(r'<\/?\w+.*?>|\d{1,2}:\d{2}:\d{2},\d{3} --> \d{1,2}:\d{2}:\d{2},\d{3}|^\d+$', re.IGNORECASE)
    
    # try:
    #     with open(file_path, 'r', encoding='utf-8') as f:
    #         lines = f.readlines()
    # except FileNotFoundError:
    #     print(f"Erreur : Fichier '{file_path}' introuvable.")
    #     return []
    
    # for line in lines:
    #     line = line.strip() 

    #     # Filtrer les lignes qui ne sont ni des numéros de séquence ni des marqueurs de temps
    #     if line and not re.match(r'^\d+$', line) and '-->' not in line:
    #         # Retirer les balises
    #         dialogue_nettoye = regex_clean.sub('', line)
            
    #         # Ajouter à la liste si il reste du texte
    #         if dialogue_nettoye.strip():
    #             dialogues.append(dialogue_nettoye.strip())

    # #Save dialogues vers fichier txt
    # dialogues_txt_path = GT_SUBS_PATH_CLEAN + TEST_MOVIE + ".srt"
    # with open(dialogues_txt_path, 'w', encoding='utf-8') as f:
    #     for dialogue in dialogues:
    #         f.write(dialogue + '\n')
    
    # return dialogues


# TEST_MOVIE = "Kill_Bill_Volume_2"
# gt_subs_clean = dialogue_clean(f"{GT_SUBS_PATH_RAW}{TEST_MOVIE}_raw.srt")
# print("Dialogues extraits:\n", gt_subs_clean[:20])



## ----------------------------------------------------------------------------------------------------------------------------------------------------

# 3. Extraction de l'audio anglais d'un film .mkv
def extract_eng_track(movie_path, audio_dir=AUDIOS_PATH):
    """
    Extrait le premier flux audio en anglais d'un fichier vidéo et le copie dans le dossier spécifié.

    Args:
        movie_path : Chemin vers le fichier vidéo (ex: 'Kill_Bill_Volume_2.mkv').
        audio_dir : Dossier de sauvegarde du fichier audio.
    
    Returns:
        str: Le chemin du fichier audio créé.
    """
 
    movie_name = os.path.splitext(os.path.basename(movie_path))[0].replace(' ', '_')
  
    
    print("-----------------------------------------------------------------")
    # Sortie de fonction s'il existe déjà
    for ext in ['aac', 'ac3']:
        audio_out_path = os.path.join(audio_dir, f"{movie_name}.{ext}")
        if os.path.isfile(audio_out_path):
            print(f"Audio déjà extrait pour {movie_name} (format: {ext}).")
            return audio_out_path.replace('\\', '/')
   


    #Vérifier existence du fichier d'entrée
    if not os.path.isfile(movie_path):
        print(f"Erreur : Fichier vidéo '{movie_path}' introuvable.")
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
            movie_path
        ]
        print("Extraction de piste audio du film: ", movie_name)
        # Subprocess pour exécuter la commande et capturer la sortie
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
    # Les formats courants sont aac, ac3.
    extension = 'aac' if codec_audio =='aac' else 'ac3' if codec_audio == 'ac3' else None
    

    # Chemin du fichier de sortie
    audio_out_path = os.path.join(audio_dir, f"{movie_name}.{extension}")

    # ffmpeg pour extraire le flux audio anglais
    if extension in ['aac', 'ac3']:
        ffmpeg_cmd = [
            'ffmpeg', 
            '-i', movie_path, 
            '-v', 'error',
            '-hide_banner',
            '-map', f'0:{index_anglais}',
            '-vn',                       # Ignorer la vidéo
            '-c:a', 'copy',              # Copie le flux audio
            audio_out_path
        ]
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




## ----------------------------------------------------------------------------------------------------------------------------------------------------

# 4. Transcription audio avec Whisper
# Obtenir la durée totale, utile pour voir l'avancée de la fonction whisper_transcript sur un long fichier
def get_audio_duration(movie_name):
    """
    Encore ffprobe pour obtenir la durée du fichier.
    """

    # Chemin du fichier audio*
    if os.path.isfile(os.path.join(AUDIOS_PATH, movie_name + ".ac3")):
        extension = ".ac3"
    elif os.path.isfile(os.path.join(AUDIOS_PATH, movie_name + ".aac")):
        extension = ".aac"
    else:
        print(f"Erreur get_audio_duration() : Fichier audio pour '{movie_name}' introuvable.")
        return 0.0
    
    audio_path = (AUDIOS_PATH + movie_name + extension)
    try:
        # Commande ffprobe pour obtenir la durée en secondes
        cmd = [
            'ffprobe', 
            '-v', 'error',
            '-hide_banner', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Erreur lors de la récupération de la durée audio : {e}")
        return 0.0


def whisper_transcript(movie_name, audio_duration):
    """
    Transcrit un fichier audio et affiche la progression, et sauvegarde en .txt

    Args:
        audio_path: Chemin vers le fichier audio.
        total_duration_seconds: Durée totale du fichier audio en secondes.
    
    Returns:
        str: Le texte complet
    """
    # Faire tourner whisper sur GPU car c'est long..
    # if torch.cuda.is_available():
    #     device = "cuda"
    # else:
    #     device = "cpu"

    
    #Chemin du fichier de sortie
    dialogues_txt_path = TRANSCRIPTS_PATH + movie_name + ".txt"

    #Créer le dossier de sortie des transcriptions
    os.makedirs(TRANSCRIPTS_PATH + movie_name, exist_ok=True)

    #pas de transcription whisper si on a deja une transcription pour ce film
    if os.path.isfile(dialogues_txt_path):
        return dialogues_txt_path.replace('\\', '/')

    # Créer le dossier de splits s'il n'existe pas
    os.makedirs(output_splits_path, exist_ok=True)
    
    # Créer le dossier de sortie s'il n'existe pas
    if os.path.isdir(GT_SUBS_PATH) and os.listdir(GT_SUBS_PATH): #Si le dossier de transcriptions pour ce film contient quelque chose, ne pas run whisper sur ce film
        return 0    
    os.makedirs(GT_SUBS_PATH, exist_ok=True)

 
    
    # Démarrer le chronomètre pour le temps réel
    start_time = time.time()
    
    print("\nDébut de la transcription. Durée totale de l'audio: ", time.strftime('%H:%M:%S', time.gmtime(audio_duration)))
    
    # Split l'audio en segments de 5 minutes (300s) pour pouvoir cancel sans faire une heure de transcription
    split_duration = 300
    audio_path = AUDIOS_PATH + movie_name + "_eng.ac3"
    output_splits_path = AUDIOS_PATH + movie_name + "/"

    print("\nDécoupage de l'audio en segments de", split_duration, "secondes...")


    try:
        split_cmd = [
                'ffmpeg', 
                '-i', audio_path,
                '-f', 'segment',
                '-segment_time', str(split_duration),
                '-c', 'copy',
                output_splits_path + "audio_split_%03d.ac3"
            ]
        subprocess.run(split_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du découpage de l'audio : {e}")
        return None
    dialogues = []
    for idx, audio_split in enumerate(os.listdir(output_splits_path)):
        print(f"\n\n{'-'*20} Transcription du segment :", audio_split)
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
        str: Transcription avec horodatage du split audio.
    """
    
    try:
        result = model.transcribe(
            str(split_path), 
            fp16=False, # Format float16 forcé pour éviter des warnings
            verbose=True, # Afficher la progression
            no_speech_threshold=0.3, #Seuil de probabilité de silence baissé (défaut 0.6)
            logprob_threshold = -0.8, # Seuil augmenté pour filtrer les segments peu fiables (défaut -1.0)
            # hallucination_silence_threshold=0.6 
        )
        
    except Exception as e:
        print(f"Erreur lors de la transcription du segment {split_path}: \n{e}")
        return None
    
    # Extraire texte et horodatages
    # dialogues = result["text"]
    segments = result["segments"] 
    transcript = []

    for segment in segments:
        start_time_seconds = segment["start"] + idx * 300  # Ajouter 5 minutes par segment précedent
        end_time_seconds = segment["end"] + idx * 300      
        text = segment["text"]
        
        # Conversion timestamp en HH:MM:SS.ms
        start_formatted = format_timestamp(start_time_seconds, always_include_hours=True, decimal_marker=',')
        end_formatted = format_timestamp(end_time_seconds, always_include_hours=True, decimal_marker=',')
        
        # Ajout à la liste
        transcript.append('\n'.join( 
            [str(idx), f'{start_formatted} --> {end_formatted}', text.strip()]
            ))

    transcript_final = '\n'.join(transcript)
    return transcript_final


## ----------------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    # Charger le modèle Whisper
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("Whisper will run on: ", device)
    # Modèle turbo: Bon pour transcription anglais-anglais
    model = whisper.load_model("turbo", device=device)


    movie_paths, movie_names = get_movie_list(MOVIES_PATH)
    number_of_movies = len(movie_paths)
    print(f"{number_of_movies} films trouvés (.mkv): ", movie_names)
    print("1. Pipeline complète: Extraction des audios et sous-titres, transcription whisper et évaluation de transcription, Prédiction de genres ") #TODO + Bert/GPT
    print("2. Extraction des sous-titres")
    print("3. Extraction des flux audio")
    print("4. Transcription à partir de flux audio")
    print("5. Évaluation des performances de transcription de Whisper (WER, CER) sur les transcriptions existantes") #TODO
    print("6. Entraînement des modèles de prédiction de genre")
    print("7. Validation / Évaluation des modèles de prédiction de genre")
    print("8. Prédiction de genres d'un film (inférence): ")

    print("Choisir le mode (1-7):")

    try: 
        mode = int(input())
    except:
        print("Veuillez entrer un nombre.")
        exit(1)
    
    if mode not in range(1, 8):
        raise ValueError("Mode invalide.")
    
    if number_of_movies == 0:
        print("Aucun film trouvé.")
        exit()
    match mode:
        case 1: # Test pipeline complète
            # TODO
            pass
        case 2: # Extraction des sous-titres
            for i in range(number_of_movies): 
                extract_dialogues(movie_paths[i], movie_names[i])
            print(f"\nDialogues extraits et sauvegardés dans {GT_SUBS_PATH}")

        case 3: # Extraction des flux audio
            for i in range(number_of_movies): 
                extract_eng_track(movie_paths[i])
            print(f"\nAudios extraits et sauvegardés dans {AUDIOS_PATH}")

        case 4: # Transcription
            for i in range(number_of_movies): 
                transcription = whisper_transcript(movie_names[i], get_audio_duration(movie_names[i]))
            pass

        case 5: #  Évaluation des performances de transcription
            # TODO
            pass

        case 6: # Entraînement des modèles de prédiction de genre
            # TODO
            pass

        case 7: # Validation / Évaluation des modèles de prédiction de genre
            # TODO
            pass

        case 8: # Prédiction de genres d'un film (inférence)
            # TODO

            # TODO choix Bert vs GPT
            pass

    

"""
        for i in range(number_of_movies):
            film_path = movie_paths[i]
            test_audio_path = extract_eng_track(film_path)
            audio_duration = get_audio_duration(movie_names[i])

            transcription = whisper_transcript(test_audio_path, audio_duration)
            if transcription:
                print("\n--- Transcription finale dans: ", TRANSCRIPTS_PATH + TEST_MOVIE + ".txt")

"""
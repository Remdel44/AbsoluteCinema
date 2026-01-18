import whisper, re, subprocess, os, time, torch, sys, pandas as pd
import whisper_eval
import imdb_genres
from pathlib import Path   

from whisper.utils import format_timestamp # Fonction de formatage des timestamps

GT_SUBS_PATH = "ground_truth_subs/"

MOVIES_PATH= "../films/"  #Hors du git car trop volumineux
AUDIOS_PATH = "input_audios/"
TRANSCRIPTS_PATH = "transcripted_subs/"

AUDIO_FORMATS = ['aac', 'ac3', 'eac3']

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
    path_movies = Path(movies_dir)

    for file in path_movies.glob("*.mkv"):
        movie_paths.append(str(file))
        # movie_file = os.path.split(file)[1]
        movie_names.append(file.stem.replace(' ', '_')) # Retirer extension / remplacer espaces

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
    mv_path = Path(movie_path)

    if not Path(movie_path).is_file():
        print(f"Erreur extract_dialogues() : Fichier vidéo '{movie_path}' introuvable.")
        exit()

    # Chemin du fichier de sortie
    subs_out_path = os.path.join(GT_SUBS_PATH, f"{movie_name}.srt")
 

    # Sortie de fonction s'il existe déjà
    if Path(subs_out_path).is_file(): return subs_out_path


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
    
    # Créer dossier de sortie s'il n'existe pas
    os.makedirs(audio_dir, exist_ok=True)
    
    print("-----------------------------------------------------------------")
    # # Sortie de fonction s'il existe déjà
    # for ext in AUDIO_FORMATS:
    #     audio_out_path = os.path.join(audio_dir, f"{movie_name}.{ext}")
    #     if os.path.isfile(audio_out_path):
    #         print(f"Audio déjà extrait pour {movie_name} (format: {ext}).")
    #         return audio_out_path.replace('\\', '/'), ext
   


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
    
    # Chemin du fichier de sortie
    audio_out_path = os.path.join(audio_dir, f"{movie_name}.{codec_audio}")

    # ffmpeg pour extraire le flux audio anglais
    if codec_audio in AUDIO_FORMATS:
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
        print('Flux audio non compatible détecté.(AAC/AC3/EAC3 nécessaire)')
        exit()

    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"\nAudio anglais extrait vers '{audio_out_path}'")

        return audio_out_path.replace('\\', '/'), codec_audio
    
    except subprocess.CalledProcessError as e:
        print(f"\nErreur lors de l'extraction FFmpeg : {e}")
        exit()



## ----------------------------------------------------------------------------------------------------------------------------------------------------

# 4. Transcription audio avec Whisper
# Obtenir la durée totale, utile pour voir l'avancée de la fonction whisper_transcript sur un long fichier
def get_audio_duration(movie_name, audio_format):
    """
    ffprobe pour obtenir la durée du fichier.
    """

    # Chemin du fichier audio
    if not os.path.isfile(os.path.join(AUDIOS_PATH, movie_name + "." + audio_format)):
        print(f"Erreur get_audio_duration() : Fichier audio pour '{movie_name}' introuvable.")
        return 0.0
    
    audio_path = (AUDIOS_PATH + movie_name + '.' + audio_format)
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


def whisper_transcript(movie_name, audio_duration, audio_format):
    """
    Transcrit un fichier audio et affiche la progression, et sauvegarde en .txt

    Args:
        audio_path: Chemin vers le fichier audio.
        total_duration_seconds: Durée totale du fichier audio en secondes.
    
    Returns:
        dialogues: La transcription complete
    """
    
    # Chemin du fichier de sortie
    dialogues_txt_path = TRANSCRIPTS_PATH + movie_name + ".txt"

    # Créer le dossier de sortie des transcriptions
    os.makedirs(TRANSCRIPTS_PATH + movie_name, exist_ok=True)

    # pas de transcription whisper si on a deja une transcription pour ce film
    if os.path.isfile(dialogues_txt_path):
        print(f"\nTranscription déjà existante pour {movie_name}.")
        return dialogues_txt_path.replace('\\', '/')
 
    
    # Démarrer le chronomètre pour le temps réel
    start_time = time.time()
    
    print(f"\nDébut de la transcription de {movie_name}. Durée totale de l'audio: ", time.strftime('%H:%M:%S', time.gmtime(audio_duration)))
    
    # Split l'audio en segments de 5 minutes (300s) pour pouvoir cancel sans faire une heure de transcription

    output_splits_path = AUDIOS_PATH + movie_name + "/"
    os.makedirs(output_splits_path, exist_ok=True)  # Créer le dossier de splits s'il n'existe pas
    split_duration = 300
    audio_path = AUDIOS_PATH + movie_name + '.' + audio_format

    try:
        split_cmd = [
                'ffmpeg', 
                '-i', audio_path,
                '-f', 'segment',
                '-segment_time', str(split_duration),
                '-c', 'copy',
                output_splits_path + "audio_split_%03d." + audio_format
            ]
        subprocess.run(split_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du découpage de l'audio : {e}")
        return None
    

    dialogues = []
    splits = sorted(os.listdir(output_splits_path))

    for idx, audio_split in enumerate(splits):
        print(f"\n\n{'-'*20} Transcription du segment :", audio_split)
        split_dialogue = transcript_audio_split(model, output_splits_path + audio_split, idx)

        if split_dialogue == None:
            print(f"Erreur lors de la transcription du segment {idx}. (dialogues=None)")
            return None
        dialogues.append(split_dialogue)

    dialogues = '\n'.join(dialogues)

    # Afficher le temps écoulé
    temps_final_str = time.strftime('%H:%M:%S', time.gmtime(audio_duration))
    duration = time.time() - start_time
    print(f"Transcription terminée (Audio total : {temps_final_str}). Temps écoulé : {time.strftime('%H:%M:%S', time.gmtime(duration))}")


    ## Sauvegarde des dialogues avec timecodes vers fichier txt
    with open(dialogues_txt_path, 'w', encoding='utf-8') as f:
        f.write(dialogues)

    # Fin de transcription -> Supprimer les dossiers temporaires, et les audios
    for audio_split in os.listdir(output_splits_path):
        os.remove(output_splits_path + audio_split)
    os.rmdir(output_splits_path)
    os.remove(audio_path)
    
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
            no_speech_threshold=0.8, #Seuil de probabilité de silence augmenté (défaut 0.6)
            logprob_threshold = -0.8, # Seuil augmenté pour filtrer les segments peu fiables (défaut -1.0)
            compression_ratio_threshold=2.0,  # détecte du texte répétitif (défaut 2.0)

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



## Main ----------------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    
    movie_paths, movie_names = get_movie_list(MOVIES_PATH)
    number_of_movies = len(movie_paths)
    print(f"{number_of_movies} films trouvés (.mkv): ", movie_names)
    print("\n")

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        mode = int(sys.argv[1])
    else:
        # print("1. Pipeline complète: Extraction des audios et sous-titres, transcription whisper et évaluation de transcription, Prédiction de genres ") #TODO + Bert/GPT
        print("1. Extraction des sous-titres")
        print("2. Extraction des flux audio et transcription Whisper")
        print("3. Évaluation des performances de transcription de Whisper (WER) sur les transcriptions existantes")
        print("4. Extraction du dataset de films (avec genres) sur IMDb")
        print("5. Entraînement des modèles de prédiction de genre") # SAVE MODELE LOCAL
        print("6. Validation / Évaluation des modèles de prédiction de genre")
        print("7. Prédiction de genres d'un film (inférence): ")
        print("8. Sortie")

        print("\nChoisir le mode:")
        try: 
            mode = int(input())
        except:
            print("Veuillez entrer un nombre.")
            exit(1)
    
        if mode not in range(1, 9):
            raise ValueError("Mode invalide.")
    
    if number_of_movies == 0:
        print("Aucun film trouvé.")
        exit()


    match mode:
        # case 1: # Test pipeline complète
        #     # TODO
        #     pass
        case 1: # Extraction des sous-titres
            for i in range(number_of_movies): 
                extract_dialogues(movie_paths[i], movie_names[i])
            print(f"\nDialogues extraits et sauvegardés dans {GT_SUBS_PATH}")

        case 2: # Transcription
            # Charger le modèle Whisper
            device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            print("Whisper will run on: ", device)
            # Modèle turbo: Bon pour transcription anglais-anglais
            model = whisper.load_model("turbo", device=device)

            audio_formats = []
            for i in range(number_of_movies): 
                audio_out_path, audio_format = extract_eng_track(movie_paths[i])
                audio_formats.append(audio_format)
            print("\nAudios extraits et sauvegardés")

            for i in range(number_of_movies): 
                transcription = whisper_transcript(movie_names[i], get_audio_duration(movie_names[i], audio_formats[i]), audio_formats[i])
            print(f"\n{number_of_movies} transcriptions effectuées")

        case 3: #  Évaluation des performances de transcription
            results, average_wer = whisper_eval.full_whisper_eval(GT_SUBS_PATH, TRANSCRIPTS_PATH)

        case 4: # Extraction du dataset de films (avec genres) sur IMDb
            df = imdb_genres.create_movie_dataset(GT_SUBS_PATH, output_csv='movies_dataset.csv')
            pass

        case 5: # Entraînement des modèles de prédiction de genre
            # TODO
            pass

        case 6: # Validation / Évaluation des modèles de prédiction de genre
            # TODO
            pass

        case 7: # Prédiction de genres d'un film (inférence)
            # TODO

            # TODO choix Bert vs GPT
            pass

        case 8: # Sortie
            exit(0)

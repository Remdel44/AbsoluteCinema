import subprocess, re



if __name__ == "__main__":

    # movie_paths, movie_names = get_movie_list(MOVIES_PATH)
    # print("Films trouvés (.mkv): ", movie_names)
    # print("1. Pipeline complète: Extraction des audios et sous-titres, transcription whisper et évaluation de transcription, Prédiction de genres ") #TODO + Bert/GPT
    # print("2. Extraction des sous-titres")
    # print("3. Extraction des flux audio")
    # print("4. Transcription à partir de flux audio")
    # print("5. Entraînement du modèle de prédiction de genre")
    # print("6. Validation / Évaluation du modèle de prédiction de genre")
    # print("7. Prédiction d'un genre (inférence): ")
    
    # print("Choisir le mode (1-7):")
    # try: mode = int(input())
    # except:
    #     print("Veuillez entrer un nombre.")
    #     exit(1)
    # match mode:
    #     case 1:
    #         print('Pipeline complète')
    #     case 2:
    #         print('Extraction des sous-titres')
    #     case _:
    #         print('Option non implémentée')

    movie_path = "../films/Killers of the Flower Moon.mkv"
    ffprobe_index_cmd = ['ffprobe', '-i', movie_path, '-hide_banner']

    try: 
        probe = subprocess.run(ffprobe_index_cmd, text=True, check=True, shell=True, capture_output=True)

        output = probe.stdout + probe.stderr # Combiner les deux sorties car ffprobe peut écrire dans stderr ?
        print("Output ffprobe:\n", f"{'-'*50}", output, f"\n{'-'*50}")
        regex = re.compile(r"Stream #0:(\d+)\((eng|en)\): Subtitle:", re.IGNORECASE)
        match = regex.search(output)
        
        if match:
            subtitle_index = match.group(1)
            print(f"Flux de sous-titres anglais trouvé à l'index : {subtitle_index}")

    except subprocess.CalledProcessError as e:
        print("Erreur lors de l'exécution de ffprobe:", e)

print(probe.stdout)
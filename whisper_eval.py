from jiwer import wer
import numpy as np
from pathlib import Path
import re

def to_secondes(t_str):
    """Convertir HH:MM:SS,mmm en total de secondes (plus simple)."""
    t_str = t_str.replace(',', '.')
    h, m, s = t_str.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def clean_text(text):
    """Retirer les balises HTML, et la ponctuation"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip().lower()


def parse_srt(txt):
    """Récupère le temps moyen et le texte entre les timestamps"""
    # 00:00:00,000 --> 00:00:00,000
    # <i>Do you find me sadistic?</i>
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[.,]\d{3})\n(.*?)(?=\n\n|\n\d+\n|$)', re.DOTALL)
    matches = pattern.findall(txt)
    data = []
    for start, end, text in matches:
        mid = (to_secondes(start) + to_secondes(end)) / 2
        txt = clean_text(text.replace('\n', ' '))
        if txt: 
            data.append({'mid': mid, 'text': txt})
    
    return data



def eval_one_whisper_transcript(gt_subs_file, transcripts__file, create_comparison__file):
    """
    Evalue un transcript Whisper en comparant avec les sous-titres.
    """

    # Ground truth
    with open(gt_subs_file, 'r', encoding='utf-8') as f:
        gt_subs = parse_srt(f.read())

    # Transcriptions Whisper 
    with open(transcripts__file, 'r', encoding='utf-8') as f:
        transcripts = parse_srt(f.read())

    # Concatener les textes entiers
    full_gt_text = [seg['text'] for seg in gt_subs]
    full_tr_text = [seg['text'] for seg in transcripts]

    all_times_gt = [seg['mid'] for seg in gt_subs]
    all_times_tr = [seg['mid'] for seg in transcripts]
        
    # jiwer échoue à aligner les dialogues, donc on calcule ligne par ligne
    gt_idx=0
    tr_idx = 0
    wer_list = []
    new_transcripts = ""

    while gt_idx < len(full_gt_text):
    # for gt_idx in range(len(full_gt_text)):
        gt_dialogue = full_gt_text[gt_idx]
        best_transcript = None
        best_wer = float('inf')
        distance = float('inf')
        best_idx = tr_idx
        gt_skip = 0

        search_start = max(0, tr_idx - 1) #Autorise retour en arrière d'une ligne, car elle peut avoir été "volée" juste avant
        search_end = min(len(full_tr_text), tr_idx + 50) # On limite la recherche à 50 phrases en avant car possible hallucinations de whisper
        
        for i in range(search_start, search_end):
            curr_distance = abs(all_times_gt[gt_idx] - all_times_tr[i])
            
            if curr_distance < distance:
                distance = curr_distance
                best_transcript = full_tr_text[i]
                best_idx = i
                best_wer = wer(gt_dialogue, best_transcript) if best_transcript else 1.0

        # On essaie de combiner avec la ligne précédente si ça améliore le WER.
        if best_idx > 0:
            combined_prev = full_tr_text[best_idx - 1] + ' ' + full_tr_text[best_idx]
            combined_wer_prev = wer(gt_dialogue, combined_prev)
            

            if combined_wer_prev < best_wer and combined_wer_prev < 1.0:
                best_transcript = combined_prev
                best_wer = combined_wer_prev
                best_idx -= 1  # Commencer depuis la ligne précédente


        # Si WER > 40% on essaie de combiner 2 lignes de transcript
        if best_wer > 0.4 and best_idx + 1 < len(full_tr_text):
            combined_tr = full_tr_text[best_idx] + ' ' + full_tr_text[best_idx + 1]
            combined_wer = wer(gt_dialogue, combined_tr)
            
            if combined_wer < best_wer and combined_wer < 1.0: # (Si WER > 1, autant ne pas décaler)
                best_transcript = combined_tr
                best_wer = combined_wer
                best_idx += 1  # Sauter la ligne suivante


        # Si WER toujours > 40% on essaie de combiner 2 lignes de GT
        if best_wer > 0.4 and gt_idx + 1 < len(full_gt_text) and best_transcript is not None:
            combined_gt = gt_dialogue + ' ' + full_gt_text[gt_idx + 1]
            combined_wer = wer(combined_gt, best_transcript)
            
            if combined_wer < best_wer and combined_wer < 1.0: #Si WER > 1, autant ne pas décaler
                best_wer = combined_wer
                gt_skip = 1  # Sauter la prochaine ligne GT


        tr_idx = best_idx + 1
        if best_transcript is not None:
            new_transcripts += best_transcript + "\n"
        else: 
            new_transcripts += "\n"
            best_wer = 1.0

        # Calculer WER pour cette ligne
        wer_list.append(best_wer)

        gt_idx += 1 + gt_skip


            
    # Créer le fichier de transcripts après ré-alignment
    with open(f"transcripted_subs/{transcripts__file.stem}_new.txt", 'w', encoding='utf-8') as f:
        f.write(new_transcripts.strip())

    if len(wer_list) == 0: average_wer = 1.0
    else: average_wer = sum(wer_list) / len(wer_list)

    if create_comparison__file:
        aligned_lines = new_transcripts.strip().split('\n')
        
        with open(f"{transcripts__file.stem}_comparison.txt", 'w', encoding='utf-8') as f:

            f.write(f"Dialogue Lines: {len(full_gt_text)}\n")
            f.write(f"Average WER : {average_wer:.2%}\n\n")
            for i in range(len(full_gt_text)):
                sub_line = full_gt_text[i] 
                tr_line = aligned_lines[i] if i < len(aligned_lines) else ""
                f.write(f"GT: {sub_line}\n")
                f.write(f"TR: {tr_line}\n")
                if i < len(wer_list):
                    f.write(f"line WER: {wer_list[i]:.2%}\n\n")

    return average_wer



def full_whisper_eval(gt_subs_folder, transcripts__folder, create_comparison__files=False):
    """
    Evalue le modèle Whisper en comparant les transcripts avec les sous-titres.
    """
    path_gt = Path(gt_subs_folder)
    transcript_path = Path(transcripts__folder)
    results = {}

    # On cherche tous les fichiers .srt
    for srt_file in path_gt.glob("*.srt"):
        # Recherche le .txt correspondant
        txt_file = transcript_path / (srt_file.stem + ".txt") # .stem = retire extension & chemin dossier

        if txt_file.exists():
            word_error_rate = eval_one_whisper_transcript(srt_file, txt_file, create_comparison__files)
            results[srt_file.name] = word_error_rate
        else:
            print(f"{srt_file.stem}.txt introuvable dans {transcripts__folder}")

    # Calcul WER moyen
    if not results: return 0
    
    average_wer = sum(results.values()) / len(results)
    print(f"\nÉvaluation Whisper: {len(results)} transcripts évalués. WER moyen: {average_wer:.2%}")
    for file_name, wer_value in results.items():
        print(f"{file_name}: WER = {wer_value:.2%}")

    return results, average_wer




if __name__ == "__main__":
    
    gt_subs_path = "ground_truth_subs/"
    transcripts_path = "transcripted_subs/"

    full_whisper_eval(gt_subs_path, transcripts_path, create_comparison__files=True)
    # for srt_file in Path(gt_subs_path).glob("Avengers*.srt"):
    #     txt_file = Path(transcripts_path) / (srt_file.stem + ".txt")
    #     print("WER: ", eval_one_whisper_transcript(srt_file, txt_file, True))
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
    print(f" nb lignes GT: {len(full_gt_text)} | nb lignes TR: {len(full_tr_text)}")

    all_times_gt = [seg['mid'] for seg in gt_subs]
    all_times_tr = [seg['mid'] for seg in transcripts]
        
    # jiwer échoue à aligner les dialogues, donc on calcule ligne par ligne
    tr_idx = 0
    wer_list = []
    new_transcripts = ""
    for gt_dialogue in full_gt_text:
        best_transcript = None
        distance = float('inf')
        
        search_start = max(0, tr_idx)
        
        for i in range(search_start, len(full_tr_text)):
            curr_distance = abs(all_times_gt[i] - all_times_tr[i])
            
            if curr_distance < distance:
                distance = curr_distance
                best_transcript = full_tr_text[i]
                tr_idx = i
            elif curr_distance > distance and i > tr_idx:
                break

        # Calculer WER pour cette ligne
        if best_transcript: 
            curr_wer = wer(gt_dialogue, best_transcript)
            new_transcripts += best_transcript + "\n"
        else: 
            curr_wer = 1.0  
            new_transcripts +="\n"

        wer_list.append(curr_wer)
            
    # Créer le fichier de transcripts après ré-alignment
    with open(f"transcripted_subs/{transcripts__file.stem}_new.txt", 'w', encoding='utf-8') as f:
        f.write(new_transcripts.strip())

    if len(wer_list) == 0: average_wer = 1.0
    else: average_wer = sum(wer_list) / len(wer_list)

    if create_comparison__file:
        with open(f"{transcripts__file}_comparison.txt", 'w', encoding='utf-8') as f:

            f.write(f"Dialogue Lines: {len(full_gt_text)}\n")
            f.write(f"Average WER : {average_wer:.2%}\n")
            for i in range(len(full_gt_text)):
                sub_line = full_gt_text[i] 
                tr_line = full_tr_text[i] if i < len(full_tr_text) else ""
                f.write(f"GT: {sub_line}\n")
                f.write(f"TR: {tr_line}\n\n")
                f.write(f"line WER: {wer_list[i]:.2%}\n")


    return average_wer



def full_whisper_eval(gt_subs_folder, transcripts__folder, create_comparison__files=True):
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
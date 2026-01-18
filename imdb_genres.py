from imdb import Cinemagoer
import time, re, pandas as pd
from pathlib import Path

SRT_FOLDER = "ground_truth_subs/"


# Créer l'instance cinemagoer
cinema = Cinemagoer()


def get_genres_cinemagoer(movie_title, year=None):
    """Récupère les genres depuis IMDb avec Cinemagoer"""
    try:
        # Rechercher le film
        results = cinema.search_movie(movie_title)
        
        if not results:
            return None, None, None
        
        # Prendre le premier résultat (ou filtrer par année)
        movie = None
        if year:
            for result in results[:3]:  # Vérifier les 3 premiers résultats
                cinema.update(result, info=['main'])
                if str(result.get('year', '')) == str(year):
                    movie = result
                    break
        
        if not movie:
            movie = results[0]
            cinema.update(movie, info=['main'])
        
        # Extraire les informations
        genres = movie.get('genres', [])
        title = movie.get('title', '')
        year = movie.get('year', '')
        # imdb_id = movie.movieID
        
        return genres, title, year #, movie.movieID
        
    except Exception as e:
        print(f"Erreur pour '{movie_title}': {e}")
        return None, None, None #, None



def create_movie_dataset(SRT_FOLDER, output_csv='movies_dataset.csv'):
    """Extrait les genres des films et exporte en .csv"""
    
    dataset = []
    notfound = []
    print(f"\nCréation du dataset des films depuis les dialogues dans '{SRT_FOLDER}'\n")
    for srt_file in list(Path(SRT_FOLDER).glob('*.srt')):        
        # Extraire titre du nom de fichier
        title = srt_file.stem
        
        # Extraire l'année dans le nom de fichier si possible
        year_match = re.search(r'\b(19|20)\d{2}\b', title)
        if year_match :
            year = year_match.group(0) 
        else: year = None

        # Récupérer genres
        genres, official_title, year = get_genres_cinemagoer(title, year)
        

        if genres:
            # Parser le SRT pourr récupérer les dialogues
            dialogues = parse_srt(srt_file)
            
            dataset.append({
                'title': official_title,
                'year': year,
                'genres': '|'.join(genres),
                'dialogues': dialogues
            })
            print(f"{'-'*80}\nTitre: {official_title} ({year}) - Genres: {', '.join(genres)}")
        else:
            notfound.append(srt_file.name)
            print(f"Film {srt_file} non trouvé sur IMDb :(")
    
    # Sauvegarder en dataframe et CSV
    df = pd.DataFrame(dataset)
    df.to_csv(output_csv, index=False)
    
    print(f"\n\nDataset créé ({output_csv}): {len(dataset)} films")

    if notfound:
        print(f"Fichiers non trouvés: {notfound}...")
    
    return df



def parse_srt(filepath):
    """Extrait le texte d'un fichier SRT"""
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        subs = f.read()
    
    lines = subs.split('\n')
    text_lines = []
    
    for line in lines:
        # Ignorer numéros et timestamps
        if re.match(r'^\d+$', line) or re.match(r'\d{2}:\d{2}:\d{2}', line):
            continue
        if line.strip():
            text_lines.append(line.strip())
    
    return ' '.join(text_lines)

# Main (tests)
if __name__ == "__main__":
    df = create_movie_dataset(SRT_FOLDER)
    
    # Charger le dataset
    df = pd.read_csv('movies_dataset.csv')
    df['genres'] = df['genres'].apply(lambda x: x.split('|'))  # Reconvertir en liste
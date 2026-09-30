import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from db import engine, text
import json

def extract_genre(url):
    page = requests.get(url).text
    data = BeautifulSoup(page, "html.parser")
    df = pd.DataFrame(columns=["genre", "path"])
    
    genre_list = data.find("ul", class_=["genres"])
    rows = genre_list.find_all("a")
    
    for gen in rows:
        genre = gen.text
        path = gen.get("href")
        
        data_dict = {
            "genre": genre,
            "path": path
        }
        
        df2 = pd.DataFrame(data_dict, index=[0])
        df = pd.concat([df, df2], ignore_index=True)

    return df

def extract_anime(url, column_attribs, genre):
    page = requests.get(url).text
    data = BeautifulSoup(page, "html.parser")
    
    df = pd.DataFrame(columns=column_attribs)
    
    page_detail = data.find("div", class_=["page"])
    
    pagination = page_detail.find("div", class_=["pagenavix"]).find_all("a", class_=["page-numbers"])
    
    total_pages = int(pagination[-2].text) if len(pagination) > 1 else 1
    for page_number in range(1, total_pages + 1):
        if page_number == 1:
            anime_list = page_detail.find_all("div", class_=["col-anime"])

            for anime in anime_list:
                title = anime.find("div", class_=["col-anime-title"]).text.strip()
                studio = anime.find("div", class_=["col-anime-studio"]).text.strip()
                episode = anime.find("div", class_=["col-anime-eps"]).text.strip()
                rating = anime.find("div", class_=["col-anime-rating"]).text.strip()
                subgenre = anime.find("div", class_=["col-anime-genre"]).text.strip().split(",")
                
                synopsis_paragraph = anime.find("div", class_=["col-synopsis"]).find_all("p")[1:-1]
                synopsis = ''
                for paragraph in synopsis_paragraph:
                    synopsis += f"{paragraph.text.strip()}\n"
                
                data_dict = {
                    "title": title,
                    "studio": studio,
                    "episode": episode,
                    "rating": rating,
                    "genre": genre,
                    "subgenre": [subgenre],
                    "synopsis": synopsis
                }
                df2 = pd.DataFrame(data_dict, index=[0])
                df = pd.concat([df, df2], ignore_index=True)
        else:
            page = requests.get(f"{url}/page/{page_number}").text
            data = BeautifulSoup(page, "html.parser")
                
            page_detail = data.find("div", class_=["page"])
            anime_list = page_detail.find_all("div", class_=["col-anime"])

            for anime in anime_list:
                title = anime.find("div", class_=["col-anime-title"]).text
                studio = anime.find("div", class_=["col-anime-studio"]).text
                episode = anime.find("div", class_=["col-anime-eps"]).text
                rating = anime.find("div", class_=["col-anime-rating"]).text
                subgenre = anime.find("div", class_=["col-anime-genre"]).text.split(",")
                
                synopsis_paragraph = anime.find("div", class_=["col-synopsis"]).find_all("p")[1:-1]
                synopsis = ''
                for paragraph in synopsis_paragraph:
                    synopsis += f"{paragraph.text}\n"
                
                data_dict = {
                    "title": title,
                    "studio": studio,
                    "episode": episode,
                    "rating": rating,
                    "genre": genre,
                    "subgenre": [subgenre],
                    "synopsis": synopsis
                }
                df2 = pd.DataFrame(data_dict, index=[0])
                df = pd.concat([df, df2], ignore_index=True)
    return df

def transform_silver_layer():
    query = """
        SELECT
            title,
            studio,
            CASE
                WHEN TRY_CONVERT(INT, REPLACE(TRIM(episode), 'eps', '')) IS NOT NULL
                    AND REPLACE(TRIM(episode), 'eps', '') != '' 
                    AND REPLACE(TRIM(episode), 'eps', '') != '-' THEN REPLACE(TRIM(episode), 'eps', '')
                ELSE 'n/a'
            END episode, 
            COALESCE(TRY_CAST(NULLIF(TRIM(rating), '') AS FLOAT), 0) rating,
            genre,
            subgenre,
            CASE
                WHEN TRIM(synopsis) != '' THEN TRIM(synopsis)
                ELSE 'n/a'
            END synopsis
        FROM (
            SELECT
                title,
                studio,
                episode,
                rating,
                genre,
                subgenre,
                synopsis,
                ROW_NUMBER() OVER(PARTITION BY title ORDER BY title) flag_title
            FROM anime_db.bronze.anime
        )t WHERE flag_title = 1
        ORDER BY title
    """
    df = pd.read_sql(query, engine)
    
    return df

def read_genre_from_db():
    query = "SELECT genre, path FROM gold.genre"
    
    df = pd.read_sql(query, engine)
    
    return df

def load_genre_to_gold_layer(df):
    df.to_sql(
        "genre",
        engine,
        schema='gold',
        if_exists="replace",
        index=False
    )

def load_anime_to_bronze_layer(df):
    df["subgenre"] = df["subgenre"].apply(json.dumps)
    
    df.to_sql(
        "anime",
        engine,
        schema="bronze",
        if_exists="replace",
        index=False,
        chunksize=1000
    )

def load_anime_to_silver_layer(df):
    df.to_sql(
        "anime",
        engine,
        schema="silver",
        if_exists="replace",
        index=False,
        chunksize=1000
    )

def load_top_rating_20():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE OR ALTER VIEW gold.top_rating_20 AS
                SELECT TOP (20) [title]
                    ,[studio]
                    ,[episode]
                    ,[rating]
                    ,[genre]
                    ,[subgenre]
                    ,[synopsis]
                FROM [silver].[anime]
                WHERE rating > 8.9
                ORDER BY rating DESC
            """)
        )

def log_progress(message):
    timestamp = f"%Y-%m-%d %H:%M:%S"
    now = datetime.now()
    date_format = now.strftime(timestamp)
    with open("./log.txt", "a") as f:
        f.write(f"{date_format}: {message}\n")
    
    print(f"{date_format}: {message}\n")

BASE_URL = "https://otakudesu.blog"

log_progress(f"Extracting genres...")
extracted_genre = extract_genre(f"{BASE_URL}/genre-list")

log_progress(f"Load data genre to gold layer...")
load_genre_to_gold_layer(extracted_genre)

log_progress(f"Read data genre from db...")
genres = read_genre_from_db()

columns_attribs = ["title", "studio", "episode", "rating", "genre", "subgenre", "synopsis"]
df_anime = pd.DataFrame(columns=columns_attribs)

log_progress(f"Extracting anime from genre...")
for genre in genres.itertuples():
    log_progress(f"{int(str(genre.Index)) + 1}. {genre.genre} genre")
    extracted_anime = extract_anime(f"{BASE_URL}{genre.path}", columns_attribs, genre.genre)
    
    df_anime = pd.concat([df_anime, extracted_anime], ignore_index=True)

log_progress(f"Load data anime to bronze layer...")
load_anime_to_bronze_layer(df_anime)

log_progress(f"Transform from bronze to silver layer...")
animes = transform_silver_layer()

log_progress(f"Load data anime to silver layer...")
load_anime_to_silver_layer(animes)

log_progress(f"Load top 20 anime by rating...")
load_top_rating_20()

import os
import time
import sqlite3

import moviepy.editor as mp
import nltk
import wikipedia
from PIL import Image
from bing_image_downloader import downloader
from gtts import gTTS
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pytrends.request import TrendReq
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def create_workspace(query):
    workspacepath = os.path.join(os.getcwd(), "workspace", query)
    os.makedirs(workspacepath, exist_ok=True)
    return workspacepath


def convert_photos_to_jpg(query, workspace_path):
    synced_dir = os.path.join(workspace_path, "synced")
    os.makedirs(synced_dir, exist_ok=True)
    os.makedirs(os.path.join(synced_dir, query), exist_ok=True)
    files = os.listdir(os.path.join(workspace_path, query))

    # Find the smallest photo in the list
    smallest_size = None
    for file_path in files:
        file_path = os.path.join(workspace_path, query, file_path)
        image = Image.open(file_path)
        if smallest_size is None or image.size[0] < smallest_size[0]:
            smallest_size = image.size

    for file_path in files:
        file_path = os.path.join(workspace_path, query, file_path)
        # Open the image file
        image = Image.open(file_path)

        # Convert the image to RGB if not already in RGB format
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize the image to a 9:16 aspect ratio
        aspect_ratio = 9 / 16
        new_width = int(smallest_size[1] * aspect_ratio)
        image = image.resize((new_width, smallest_size[1]), resample=Image.LANCZOS)

        # Save the image to the synced folder as JPEG
        filename = os.path.basename(file_path)
        new_file_path = os.path.join(synced_dir, query, os.path.splitext(filename)[0] + ".jpg")
        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
        image.save(new_file_path, "JPEG")
        os.remove(file_path)


def get_trending_searches():
    pytrend = TrendReq()
    return pytrend.trending_searches(pn='united_states')


def get_wikipedia_summary(query):
    try:
        data = wikipedia.page(title=query, auto_suggest=True)
        summary = data.summary
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options
        data = wikipedia.page(title=options[1], auto_suggest=True)
        summary = data.summary
        return summary
    except wikipedia.exceptions.PageError as e:
        print(f"Error: {e}")


def generate_keywords(text):
    # Tokenize the text into individual words
    tokens = word_tokenize(text)

    # Remove stopwords (common words that don't carry much meaning)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word.lower() not in stop_words]

    # Perform part-of-speech tagging
    tagged_tokens = nltk.pos_tag(filtered_tokens)

    # Extract nouns and adjectives as keywords
    keywords = [word for word, pos in tagged_tokens if pos.startswith('N') or pos.startswith('J')]

    return keywords


def short_keywords(keyword_list):
    """
    This function takes a list of keywords and returns a shorter list of keywords,
    up to a maximum of 500 characters. The keywords are separated by commas.

    Args:
      keyword_list: A list of strings.

    Returns:
      A string of keywords, separated by commas.
    """
    # Generate a string from list with commas separating the keywords.
    keyword_string = ','.join(keyword_list)
    # Get the length of the keyword string.
    length = len(keyword_string)

    # If the keyword string is less than or equal to 500 characters, return it as a string.
    if length <= 500:
        return keyword_string
    else:
        new_list = []
        total_length = 0

        # Iterate through the keyword_list and add keywords to new_list until the total length exceeds 500 characters.
        for keyword in keyword_list:
            # Check if adding the current keyword exceeds the maximum length of 500 characters.
            if total_length + len(keyword) + len(new_list) <= 500:
                new_list.append(keyword)
                total_length += len(keyword)
            else:
                break

        # Return the new list of keywords as a string, separated by commas.
        return ','.join(new_list)



def download_images(query, workspace_path):
    downloader.download(query, limit=5, output_dir=os.path.join(workspace_path), adult_filter_off=True,
                        force_replace=False, timeout=10, verbose=False)


def create_audio(summary, workspace_path):
    # Set up audio
    language = "en"
    speech = gTTS(text=summary, lang=language, slow=False)
    audio_path = os.path.join(workspace_path, "synced", "speak.mp3")
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    speech.save(audio_path)


def create_video(query, workspace_path):
    audio_path = os.path.join(workspace_path, "synced", "speak.mp3")
    images_path = os.path.join(workspace_path, "synced", query)
    output_path = os.path.join(workspace_path, "video", query, "clip.mp4")
    os.makedirs(os.path.join(workspace_path, "video", query), exist_ok=True)

    # Load audio file and get duration
    audio = mp.AudioFileClip(audio_path)

    audio_duration = audio.duration

    # Load images and calculate duration of each image
    images = os.listdir(images_path)
    per_image_duration = audio_duration / len(images)
    clips = []
    # Create a video
    for i, image in enumerate(images):
        clip = mp.ImageClip(img=os.path.join(images_path, image), duration=per_image_duration)
        clip.fps = 24
        clips.append(clip)

    video = mp.concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)

    # Save the video
    video.write_videofile(output_path, fps=24, codec="mpeg4")


def upload_video_youtube(file_path, description: str, title: str, keywords: str):
    try:
        wait = WebDriverWait(driver, 10)

        create_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#create-icon > div')))
        create_icon.click()
        time.sleep(1)

        text_item = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#text-item-0 yt-formatted-string')))
        text_item.click()
        time.sleep(1)

        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(file_path)
        time.sleep(1)

        # Wait for the details section to be visible
        wait.until(EC.visibility_of_element_located((By.ID, 'reuse-details-button')))
        time.sleep(1)

        # Fill in the video title
        title_input = driver.find_element(By.XPATH,
                                          '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-basics/div[1]/ytcp-social-suggestions-textbox/ytcp-form-input-container/div[1]/div[2]/div/ytcp-social-suggestion-input/div')
        time.sleep(0.5)
        title_input.clear()
        time.sleep(0.5)
        title_input.send_keys(title)
        time.sleep(1)

        # Fill in the video description
        description_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.description ytcp-social-suggestion-input > div')))
        description_input.send_keys(description)
        time.sleep(1)

        # Set the video as not made for kids
        not_made_for_kids_radio = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, 'ytkc-made-for-kids-select tp-yt-paper-radio-button:nth-of-type(2) ytcp-ve')))
        not_made_for_kids_radio.click()
        time.sleep(1)

        # Enable comments on the video
        toggle_comments_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#toggle-button > div')))
        toggle_comments_button.click()

        time.sleep(2)

        # Add tags to the video
        tags_input = wait.until(EC.visibility_of_element_located((By.XPATH,
                                                                  '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-advanced/div[4]/ytcp-form-input-container/div[1]/div/ytcp-free-text-chip-bar/ytcp-chip-bar/div/input')))
        tags_input.send_keys(keywords)
        time.sleep(1)

        next_button = driver.find_element(By.XPATH, '//*[@id="next-button"]')
        for i in range(3):
            next_button.click()
            time.sleep(1)

        public_button = wait.until(EC.element_to_be_clickable((By.NAME, 'PUBLIC')))
        # Click the "Public" button
        public_button.click()
        time.sleep(1)

        done_button = wait.until(EC.element_to_be_clickable((By.ID, "done-button")))
        done_button.click()
        time.sleep(3)
        close_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//ytcp-button[@id="close-button"]')))

        # Click the "Kapat" button
        close_button.click()
        time.sleep(3)
    except Exception as e:
        print(e)
        time.sleep(500)


def generate_chrome_options():
    username = os.getlogin()
    # Configure Chrome options
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless')  # Run Chrome in headless mode (without a visible browser window)
    chrome_options.add_argument('--no-sandbox')  # Bypass OS security model
    chrome_options.add_argument('--disable-dev-shm-usage')  # Disable "DevShmUsage" flag
    chrome_options.add_argument(fr'--user-data-dir=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data')
    chrome_options.add_argument(
        fr'--profile-directory=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data\\Default')
    return chrome_options


def update_nltk_files():
    import nltk
    nltk.download('averaged_perceptron_tagger')
    # Download the stopwords corpus if not already downloaded
    nltk.download('stopwords')

    # Download the Punkt tokenizer if not already downloaded
    nltk.download('punkt')


if __name__ == "__main__":
    update_nltk_files()
    # Start ChromeDriver with options.
    driver = webdriver.Chrome(executable_path=os.path.join("driver"), options=generate_chrome_options())
    driver.get("https://studio.youtube.com/")
    # Connect to the SQLite database
    conn = sqlite3.connect('processed_trends.db')
    cursor = conn.cursor()

    # Create a table to store processed trends if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS trends (trend_name text)''')
    conn.commit()
    trends = get_trending_searches()

    for query in trends.iloc[:, 0]:
        # Check if the trend has already been processed
        cursor.execute("SELECT * FROM trends WHERE trend_name=?", (query,))
        result = cursor.fetchone()
        if result:
            pass

        else:
            # Process the trend
            workspace_path = create_workspace(query)
            audio_path = os.path.join(workspace_path, "synced", "speak.mp3")
            images_path = os.path.join(workspace_path, "synced")
            summary = get_wikipedia_summary(query)
            if summary:
                download_images(query, workspace_path)
                convert_photos_to_jpg(query, workspace_path)
                create_audio(summary, workspace_path)
                create_video(query, workspace_path)
                video_path = os.path.join(workspace_path, "video", query, "clip.mp4")  # Path to the video file
                meta_tags = generate_keywords(summary)
                shortened_tags_result = short_keywords(meta_tags)
                print(shortened_tags_result)
                for tag in shortened_tags_result:
                    print(tag)

                upload_video_youtube(file_path=video_path, description=summary, title=query,
                                     keywords=shortened_tags_result)

                # Store the processed trend in the database
                cursor.execute("INSERT INTO trends VALUES (?)", (query,))
                conn.commit()

    # Close the database connection
    conn.close()
    exit()

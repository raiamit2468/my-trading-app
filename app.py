import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import time

# Streamlit Secrets se API key automatic padhega
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error("API Key secrets me set nahi hai!")

st.title("AI Trading Chart Analyzer")
st.write("Upload chart screenshot for Buy/Sell signals")

uploaded_file = st.file_uploader("Upload Chart Image", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)

    # Bada screenshot Gemini ko slow/timeout kar deta hai — resize karke bhejo
    max_width = 1024
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, int(image.height * ratio)))

    st.image(image, caption='Uploaded Chart', use_container_width=True)

    if st.button('Analyze Chart'):
        prompt = """
        You are an expert technical analyst. Analyze this chart image:
        1. Current Trend & Patterns identified
        2. Signal: BUY / SELL / WAIT
        3. Entry Price, Target Price, and Stop Loss
        4. Risk to Reward Ratio
        Keep it clear and precise.
        """

        # 503 / timeout ke liye retry with longer deadline
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with st.spinner(f"Analyzing... (attempt {attempt + 1}/{max_retries})"):
                    response = client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=[prompt, image],
                        config=types.GenerateContentConfig(
                            http_options=types.HttpOptions(timeout=60000)  # 60 sec
                        ),
                    )
                st.subheader("Analysis & Signal:")
                st.write(response.text)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    st.warning(f"Server busy hai, retry ho raha hai... ({attempt + 1}/{max_retries})")
                    time.sleep(3)
                else:
                    st.error("Gemini server abhi available nahi hai. Thodi der baad try karo.")
                    st.exception(e)

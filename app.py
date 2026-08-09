import streamlit as st
from google import genai
from PIL import Image

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
    st.image(image, caption='Uploaded Chart', use_container_width=True)
    
    if st.button('Analyze Chart'):
        try:
            prompt = """
            You are an expert technical analyst. Analyze this chart image thoroughly and provide:
            1. Current Trend & Patterns identified
            2. Signal: BUY / SELL / WAIT
            3. Entry Price, Target Price, and Stop Loss
            4. Risk to Reward Ratio
            Keep it clear and precise.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, image]
            )
            st.subheader("Analysis & Signal:")
            st.write(response.text)
        except Exception as e:
            
st.exception(e)

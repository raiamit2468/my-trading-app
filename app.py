import streamlit as st
import google.generativeai as genai
from PIL import Image

# Yahan apni Google AI Studio ki Gemini API key daalein
genai.configure(api_key="YOUR_FREE_GEMINI_API_KEY")

st.title("AI Trading Chart Analyzer")
st.write("Upload chart screenshot for Buy/Sell signals")

uploaded_file = st.file_uploader("Upload Chart Image", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='Uploaded Chart', use_column_width=True)
    
    if st.button('Analyze Chart'):
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        You are an expert technical analyst. Analyze this chart image thoroughly and provide:
        1. Current Trend & Patterns identified
        2. Signal: BUY / SELL / WAIT
        3. Entry Price, Target Price, and Stop Loss
        4. Risk to Reward Ratio
        Keep it clear and precise.
        """
        
        response = model.generate_content([prompt, image])
        st.subheader("Analysis & Signal:")
        st.write(response.text)

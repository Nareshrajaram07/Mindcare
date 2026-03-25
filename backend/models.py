# models.py

from groq import Groq
import requests
import base64
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import PyPDF2


# -------------------------------
# 🧠 TEXT AI (Groq)
# -------------------------------
class GroqChatClient:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
    
    def chat(self, specialist_type, patient_data):
        prompt = SPECIALIST_PROMPTS.get(specialist_type, "")

        user_input = f"""
You are a professional {specialist_type}.

Patient Data:
{patient_data}

Give:
1. Possible causes
2. Risk level (Low/Medium/High)
3. What to do next

Do NOT prescribe medicines.
Keep it simple and safe.
"""

        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",  # ✅ latest working model
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ]
        )

        return response.choices[0].message.content


# -------------------------------
# 🖼️ IMAGE AI (Mistral Vision)
# -------------------------------
class VisionModelClient:
    def __init__(self, mistral_api_key=None):
        self.api_key = mistral_api_key
        self.url = "https://api.mistral.ai/v1/chat/completions"

    def encode_image(self, filepath):
        with open(filepath, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def analyze_skin_condition(self, filepath, patient_info):
        try:
            base64_image = self.encode_image(filepath)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "pixtral-12b-2409",  # ✅ vision model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Analyze this skin condition: {patient_info}"},
                            {
                                "type": "image_url",
                                "image_url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        ]
                    }
                ]
            }

            response = requests.post(self.url, headers=headers, json=payload)

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"Error analyzing image: {response.text}"

        except Exception as e:
            return f"Skin analysis failed: {str(e)}"

    def analyze_xray(self, filepath, patient_info):
        try:
            base64_image = self.encode_image(filepath)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "pixtral-12b-2409",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Analyze this X-ray: {patient_info}"},
                            {
                                "type": "image_url",
                                "image_url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        ]
                    }
                ]
            }

            response = requests.post(self.url, headers=headers, json=payload)

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"Error analyzing image: {response.text}"

        except Exception as e:
            return f"X-ray analysis failed: {str(e)}"


# -------------------------------
# 📄 RAG PIPELINE (Future use)
# -------------------------------
class MedicalRAGPipeline:
    def __init__(self, groq_api_key, collection_name="medical_docs"):
        self.model = SentenceTransformer('all-mpnet-base-v2')  # 🔥 upgraded
        self.index = faiss.IndexFlatL2(768)                    # 🔥 updated dimension
        self.text_chunks = []
        self.groq_client = GroqChatClient(groq_api_key)
    # -------------------------
    # 📄 Extract text from PDF
    # -------------------------
    def extract_text(self, filepath):
        text = ""
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text

    # -------------------------
    # ✂️ Split into chunks
    # -------------------------
    def chunk_text(self, text, chunk_size=300):
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i:i+chunk_size]))
        return chunks

    # -------------------------
    # 📥 Process PDF
    # -------------------------
    def process_pdf(self, filepath, document_id=None):
        text = self.extract_text(filepath)
        chunks = self.chunk_text(text)

        embeddings = self.model.encode(chunks)

        self.index.add(np.array(embeddings))
        self.text_chunks.extend(chunks)

    # -------------------------
    # 🔍 Retrieve relevant chunks
    # -------------------------
    def retrieve(self, query, top_k=3):
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_embedding), top_k)

        results = [self.text_chunks[i] for i in indices[0] if i < len(self.text_chunks)]
        return results

    # -------------------------
    # 🤖 Ask question
    # -------------------------
    def query_documents(self, query, patient_info):
        context_chunks = self.retrieve(query)

        context = "\n\n".join(context_chunks)

        prompt = f"""
You are a medical AI assistant.

Patient Info:
{patient_info}

Use ONLY the context below to answer.

Context:
{context}

Question:
{query}

Give:
- Explanation
- Risk level
- Next steps
"""

        return self.groq_client.chat("general_practitioner", prompt)

    # -------------------------
    # 🗑️ Cleanup
    # -------------------------
    def delete_collection(self):
        self.index.reset()
        self.text_chunks = []

# -------------------------------
# 🧾 PROMPTS
# -------------------------------
SPECIALIST_PROMPTS = {
    "general_practitioner": "You are a general doctor. Give safe medical advice.",
    "cardiologist": "You are a heart specialist. Focus on cardiac symptoms.",
    "dermatologist": "You are a skin specialist.",
    "orthopedic": "You are a bone and joint specialist.",
    "gynecologist": "You are a women's health specialist.",
    "neurologist": "You are a brain and nervous system specialist.",
    'pulmonology': """

    You are a Pulmonologist AI assistant.

    Focus on:
    - Breathing issues
    - Lung infections
    - Asthma, COPD
    - Oxygen levels

    Provide:
    - Possible causes
    - Risk level
    - Recommended tests
    - Basic precautions

    Keep answers simple and medically safe.
    """
}
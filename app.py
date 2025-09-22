import os
import requests
import google.generativai as genai
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno (las API keys)
load_dotenv()

# Configurar la App Flask
app = Flask(__name__)

# Configurar la API de Google Gemini
# Asegúrate de que la clave GEMINI_API_KEY está en tu archivo .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# Ruta principal que muestra la página web
@app.route('/')
def index():
    return render_template('index.html')

# Ruta de la API que procesará la solicitud principal
@app.route('/get_weather_narrative', methods=['POST'])
def get_weather_narrative():
    try:
        data = request.get_json()
        city = data.get('city')
        personality = data.get('personality', 'alegre')

        if not city:
            return jsonify({'error': 'El nombre de la ciudad es requerido.'}), 400
        
        weather_api_key = os.getenv('OPENWEATHER_API_KEY')
        
        # --- 1. OBTENER DATOS DEL TIEMPO ACTUAL ---
        current_weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric&lang=es"
        weather_response = requests.get(current_weather_url)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        description = weather_data['weather'][0]['description']
        temp = weather_data['main']['temp']
        lat = weather_data['coord']['lat']
        lon = weather_data['coord']['lon']

        # --- 2. GENERAR NARRATIVA CON IA ---
        prompt_base = "Actúa como un meteorólogo carismático y creativo para 'eltiempo.ai'. Transforma datos técnicos en una narrativa breve (40-50 palabras)."
        prompt_modifiers = {
            'alegre': "Usa un tono muy entusiasta y optimista. ¡Haz que el día suene genial!",
            'poetico': "Describe el tiempo de forma lírica, con metáforas y un lenguaje evocador.",
            'tecnico': "Sé preciso y educativo. Explica la situación con términos meteorológicos pero de forma comprensible.",
            'sarcástico': "Utiliza un humor irónico y un poco cínico para describir el tiempo. Sé divertido.",
            'para_ninos': "Explica el tiempo como si hablaras con un niño de 6 años, con ejemplos sencillos y animados."
        }
        prompt_modifier = prompt_modifiers.get(personality, prompt_modifiers['alegre'])

        full_prompt = f"""
        {prompt_base}
        **Tono a utilizar**: {prompt_modifier}
        Basado en los siguientes datos para {city}:
        - Condición: {description}, Temperatura: {temp}°C.
        Crea el pronóstico narrativo. Sé conciso y no repitas el nombre de la ciudad.
        """
        ai_response = model.generate_content(full_prompt)
        narrative = ai_response.text

        # --- 3. OBTENER Y PROCESAR LA PREVISIÓN PARA 5 DÍAS ---
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={weather_api_key}&units=metric&lang=es"
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        forecast_list = []
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        processed_dates = []
        for forecast in forecast_data['list']:
            timestamp = datetime.fromtimestamp(forecast['dt'])
            if forecast['dt_txt'].endswith("12:00:00") and timestamp.date() not in processed_dates:
                if timestamp.date() == datetime.today().date():
                    continue
                
                processed_dates.append(timestamp.date())
                day_name = dias_semana[timestamp.weekday()]
                
                forecast_list.append({
                    "day": day_name,
                    "temp": forecast['main']['temp'],
                    "icon": forecast['weather'][0]['icon']
                })
        
        processed_forecast = forecast_list[:5]

        # --- 4. DEVOLVER LA RESPUESTA COMBINADA ---
        return jsonify({
            'narrative': narrative,
            'forecast': processed_forecast
        })

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            return jsonify({'error': f'No se pudo encontrar la ciudad: {city}.'}), 404
        return jsonify({'error': f'Error al obtener los datos del tiempo: {str(err)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Ha ocurrido un error inesperado: {str(e)}'}), 500

@app.route('/get_daily_narrative', methods=['POST'])
def get_daily_narrative():
    try:
        data = request.get_json()
        daily_data = data.get('daily_data')
        personality = data.get('personality', 'alegre')

        if not daily_data:
            return jsonify({'error': 'Faltan los datos del día.'}), 400
        
        day_name = daily_data.get('day')
        temp = daily_data.get('temp')
        icon_code = daily_data.get('icon')
        
        prompt_base = "Actúa como un meteorólogo carismático para 'eltiempo.ai'. Crea una narrativa breve (30-40 palabras) sobre la previsión del tiempo."
        
        prompt_modifiers = {
            'alegre': "Usa un tono entusiasta y optimista.",
            'poetico': "Describe la previsión de forma lírica.",
            'tecnico': "Sé preciso y educativo.",
            'sarcástico': "Utiliza un humor irónico.",
            'para_ninos': "Explica la previsión como si hablaras con un niño."
        }
        prompt_modifier = prompt_modifiers.get(personality, prompt_modifiers['alegre'])

        full_prompt = f"""
        {prompt_base}
        **Tono a utilizar**: {prompt_modifier}
        La previsión para el próximo **{day_name}** indica una temperatura aproximada de **{temp}°C**.
        El código interno del icono del tiempo es '{icon_code}'. Usa este código para inferir si estará soleado, nublado, lluvioso, etc., pero **nunca menciones el código en tu respuesta final**.
        Crea la narrativa para ese día futuro. Sé conciso y directo.
        """
        
        ai_response = model.generate_content(full_prompt)
        narrative = ai_response.text

        return jsonify({'narrative': narrative})

    except Exception as e:
        return jsonify({'error': f'Ha ocurrido un error inesperado: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
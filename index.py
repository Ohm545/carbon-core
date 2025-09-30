from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import json
import time
from datetime import datetime
import threading
import os

load_dotenv() 
app = Flask(__name__)
CORS(app)

# API Configuration
RAILRADAR_API_KEY = os.getenv("rr_api_key")
GEMINI_API_KEY = os.getenv("g_api_key")

# Target stations to monitor
TARGET_STATIONS = ["PMD", "TIM", "RRJ", "PLU"]

# 32 Trains data
TRAINS_ARRAY = {
  "count": 32,
  "trains": [
    {"name": "Karaikal - Mumbai LTT Weekly Express (PT)", "number": "11018", "type": "Mail/Express"},
    {"name": "MGR Chennai Central - Mumbai LTT SF Express (PT)", "number": "12164", "type": "SuperFast"},
    {"name": "Tirupati - Secunderabad SF Express (PT)", "number": "12731", "type": "SuperFast"},
    {"name": "Rayalaseema SF Express (PT)", "number": "12793", "type": "SuperFast"},
    {"name": "Mysuru - Jaipur SF Express (PT)", "number": "12975", "type": "SuperFast"},
    {"name": "Nagercoil - Mumbai CSMT Express (via Renigunta) (PT)", "number": "16352", "type": "Mail/Express"},
    {"name": "Kanniyakumari - Pune Express (PT)", "number": "16382", "type": "Mail/Express"},
    {"name": "KSR Bengaluru - Hazur Sahib Nanded Express", "number": "16593", "type": "Mail/Express"},
    {"name": "Coimbatore - Rajkot Express (PT)", "number": "16614", "type": "Mail/Express"},
    {"name": "MGR Chennai Central - SSS Hubballi Express (via Ballari) (PT)", "number": "17314", "type": "Mail/Express"},
    {"name": "Haripriya Express (PT)", "number": "17415", "type": "Mail/Express"},
    {"name": "Tirupati - Sainagar Shirdi Weekly Express (PT)", "number": "17417", "type": "Mail/Express"},
    {"name": "Tirupati - Vasco-Da-Gama Weekly Express", "number": "17419", "type": "Mail/Express"},
    {"name": "Yelahanka - Kacheguda Express (PT)", "number": "17604", "type": "Mail/Express"},
    {"name": "Tirupati - Aurangabad Weekly Express", "number": "17622", "type": "Mail/Express"},
    {"name": "Prashanti Express (PT)", "number": "18464", "type": "Mail/Express"},
    {"name": "MGR Chennai Central - Ekta Nagar (Kevadiya) Weekly SF Express (PT)", "number": "20919", "type": "SuperFast"},
    {"name": "MGR Chennai Central - Ahmedabad SF Express (PT)", "number": "20953", "type": "SuperFast"},
    {"name": "Madurai - Mumbai LTT Weekly SF Express (PT)", "number": "22102", "type": "SuperFast"},
    {"name": "Chennai Egmore - Mumbai CSMT SF Mail (PT)", "number": "22158", "type": "SuperFast"},
    {"name": "MGR Chennai Central - Mumbai CSMT SF Express (PT)", "number": "22160", "type": "SuperFast"},
    {"name": "MGR Chennai Central - Mumbai LTT Weekly SF Express (PT)", "number": "22180", "type": "SuperFast"},
    {"name": "Tirupati - Jammu Tawi Humsafar Express", "number": "22705", "type": "Humsafar"},
    {"name": "MGR Chennai Central - Ahmedabad Humsafar Express", "number": "22919", "type": "Humsafar"},
    {"name": "Tirupati - Hubballi Intercity Passenger", "number": "57401", "type": "Passenger"},
    {"name": "Hindupur - Guntakal DEMU", "number": "77214", "type": "DEMU"},
    {"name": "MGR Chennai Central - Mumbai CSMT Special Fare Summer Special (PT)", "number": "01016", "type": "Mail/Express"},
    {"name": "Tirupati - Solapur Special Fare Special", "number": "01438", "type": "Mail/Express"},
    {"name": "Arsikere - Secunderabad Special Fare Special", "number": "07080", "type": "Mail/Express"},
    {"name": "Villupuram - Kacheguda Special Fare Special", "number": "07425", "type": "Mail/Express"},
    {"name": "Tirupati - Hisar Special Fare AC Special", "number": "07717", "type": "AC Express"},
    {"name": "Tiruchchirappalli - Ahmedabad Special Fare Special", "number": "09420", "type": "Mail/Express"}
  ]
}

# Global storage for processed data
processed_trains_data = {}
gemini_analysis_results = {}
all_trains_table_data = []
background_processing_active = False  # Flag to control background processing

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

def fetch_train_data(train_number):
    """
    Fetch data for a single train
    """
    try:
        response = requests.get(
            f"https://railradar.in/api/v1/trains/{train_number}",
            headers={"x-api-key": RAILRADAR_API_KEY},
            params={
                "journeyDate": datetime.now().strftime("%Y-%m-%d"),
                "dataType": "live",
                "provider": "railradar",
                "userId": ""
            },
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ HTTP {response.status_code} for train {train_number}")
            return None
            
    except Exception as e:
        print(f"💥 Error fetching train {train_number}: {e}")
        return None

def ask_gemini_analyze_single_train(train_number, train_data):
    """
    Send single train data to Gemini for analysis and extract table data
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        prompt = f"""
        CURRENT TIME: {current_time}
        TARGET STATIONS TO MONITOR: {TARGET_STATIONS}

        Analyze this train data and extract information for the control center table.

        TRAIN DATA:
        {json.dumps(train_data, indent=2)}

        INSTRUCTIONS:
        1. Extract the following information for the table:
           - Train Name
           - Current Location (station name)
           - Scheduled time at current location or next major station
           - Actual time at current location or next major station  
           - Delay in minutes (calculate from the data)
           - Priority (estimate based on train type and delay: High/Medium/Low)
           - Status (Running, Delayed, On Time, etc.)

        2. Calculate delay by comparing scheduled vs actual times in the data
        3. For priority: 
           - High: SuperFast/Express trains with <10 min delay
           - Medium: Mail/Express with 10-30 min delay or SuperFast with >10 min delay
           - Low: Passenger trains or trains with >30 min delay
        4. Consider the trains which are delay currently not before. So use current time and then calculate what is delay at current time
            and at current which trains are delay, return that only no need to return befor delayed trains.

        Return ONLY valid JSON format without any markdown:
        {{
          "train_number": "{train_number}",
          "train_name": "string",
          "table_data": {{
            "name": "string (train name)",
            "current_location": "string (station name)",
            "scheduled": "string (HH:MM format)",
            "actual": "string (HH:MM format)", 
            "delay": "number (minutes)",
            "priority": "string (High/Medium/Low)",
            "status": "string"
          }},
          "analysis_time": "{current_time}",
          "is_near_target_stations": true/false,
          "current_location_detail": {{
            "station_code": "string",
            "station_name": "string",
            "status": "string"
          }},
          "next_station": {{
            "code": "string",
            "name": "string",
            "scheduled_arrival": "string",
            "estimated_arrival": "string",
            "delay_minutes": number
          }},
          "reason": "string"
        }}
        """
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        print(f"🤖 Sending train {train_number} to Gemini for analysis...")
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            gemini_response = result['candidates'][0]['content']['parts'][0]['text']
            cleaned_response = gemini_response.replace('```json', '').replace('```', '').strip()
            parsed_response = json.loads(cleaned_response)
            print(f"✅ Gemini analysis completed for train {train_number}!")
            return parsed_response
        else:
            print(f"❌ Gemini API Error for train {train_number}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"💥 Gemini analysis error for train {train_number}: {str(e)}")
        return None

def ask_gemini_generate_solutions(train_data, delay_reason):
    """
    Ask Gemini to generate solutions for delayed trains to improve throughput
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        json_template = '''{
"solutions": [
{
"solution_type": "string (platform_reassignment/speed_adjustment/route_optimization/congestion_management)",
"description": "string (exact actionable steps with station, track, timing, speed if applicable)",
"expected_impact_minutes": number,
"priority": "High/Medium/Low",
"implementation_complexity": "Low/Medium/High"
}
],
"overall_confidence": number (0-100),
"throughput_improvement_potential": "string (short, realistic description)"
}'''
        prompt = f"""
You are a railway operations expert. Analyze the delayed train and generate multiple practical, actionable solutions to recover lost time and improve overall throughput.

TRAIN DATA: {json.dumps(train_data, indent=2)}
DELAY REASON: {delay_reason}

Guidelines:

Directly address the cause of the delay—each solution must solve the actual problem.

Provide 2–4 feasible solutions, sorted by priority and expected impact, so that a human operator can easily choose the most practical one.

Be concrete and implementable:

Example: 'Train X should switch to track Y at station Z at HH:MM'

Example: 'Increase speed by X km/h between stations A and B for Y km'

Example: 'Hold train X at station Z for X minutes to allow precedence'
Avoid vague or infeasible suggestions like 'don't hold at station'.

Operational levers to consider:

Routing & Track Usage: track change, loop line, siding, platform reassignment

Train Sequencing & Precedence: crossing adjustment, overtake scheduling, reschedule precedence

Speed & Timing Control: speed adjustments, temporary hold, staggered departures

Congestion Management: avoid bottlenecks by coordinating train flow

Solution constraints:

Must be feasible under current network and schedule constraints

Should recover lost time and maximize overall throughput

Provide only actionable, implementable steps; no pseudo-code or placeholders

Output format (strict JSON, no markdown):

{json_template}
"""

        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        print(f"🤖 Generating solutions for delayed train...")
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            gemini_response = result['candidates'][0]['content']['parts'][0]['text']
            cleaned_response = gemini_response.replace('```json', '').replace('```', '').strip()
            parsed_response = json.loads(cleaned_response)
            print(f"✅ Solutions generated successfully!")
            return parsed_response
        else:
            print(f"❌ Gemini solutions generation error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"💥 Solutions generation error: {str(e)}")
        return None

def process_trains_sequentially():
    """
    Process all 32 trains sequentially and send each to Gemini individually
    """
    global processed_trains_data, gemini_analysis_results, all_trains_table_data
    
    print("🚆 STARTING SEQUENTIAL PROCESSING OF 32 TRAINS")
    print("=" * 60)
    
    train_numbers = [train["number"] for train in TRAINS_ARRAY["trains"]]
    successful_trains = []
    all_trains_table_data = []  # Reset table data
    
    for i, train_number in enumerate(train_numbers, 1):
        print(f"\n[{i}/32] Processing train {train_number}...")
        
        # Step 1: Fetch train data from RailRadar
        train_data = fetch_train_data(train_number)
        
        if train_data:
            # Step 2: Send to Gemini for analysis
            gemini_analysis = ask_gemini_analyze_single_train(train_number, train_data)
            
            if gemini_analysis:
                # Store the processed data
                processed_trains_data[train_number] = {
                    'raw_data': train_data,
                    'gemini_analysis': gemini_analysis,
                    'processed_at': datetime.now().isoformat()
                }
                
                # Add to table data
                if 'table_data' in gemini_analysis:
                    table_entry = gemini_analysis['table_data']
                    table_entry['train_number'] = train_number
                    all_trains_table_data.append(table_entry)
                
                successful_trains.append(train_number)
                print(f"   ✅ Successfully processed train {train_number}")
                
                # Generate solutions for delayed trains
                delay = gemini_analysis.get('table_data', {}).get('delay', 0)
                if delay > 10:  # Generate solutions for trains with >10 min delay
                    solutions = ask_gemini_generate_solutions(train_data, gemini_analysis.get('reason', 'Unknown delay'))
                    if solutions:
                        processed_trains_data[train_number]['solutions'] = solutions
                
                # Update global analysis results
                if gemini_analysis.get('is_near_target_stations'):
                    if 'trains_near_stations' not in gemini_analysis_results:
                        gemini_analysis_results['trains_near_stations'] = []
                    
                    gemini_analysis_results['trains_near_stations'].append({
                        'train_number': train_number,
                        'train_name': gemini_analysis.get('train_name', 'Unknown'),
                        'current_location': gemini_analysis.get('current_location_detail', {}),
                        'next_station': gemini_analysis.get('next_station', {}),
                        'status': gemini_analysis.get('table_data', {}).get('status', 'Unknown'),
                        'delay_minutes': delay,
                        'reason': gemini_analysis.get('reason', 'N/A')
                    })
            else:
                print(f"   ❌ Gemini analysis failed for train {train_number}")
        else:
            print(f"   ❌ Failed to fetch data for train {train_number}")
        
        # Add delay to avoid rate limiting
        time.sleep(2)
    
    # Update summary
    gemini_analysis_results['summary'] = {
        'total_trains_analyzed': len(successful_trains),
        'trains_near_target_stations': len(gemini_analysis_results.get('trains_near_stations', [])),
        'analysis_time': datetime.now().isoformat(),
        'target_stations': TARGET_STATIONS
    }
    
    print(f"\n📊 Processing completed: {len(successful_trains)}/{len(train_numbers)} trains successful")
    print(f"🎯 Trains near target stations: {len(gemini_analysis_results.get('trains_near_stations', []))}")

def start_background_processing():
    """Start background processing of trains"""
    global background_processing_active
    
    def process_job():
        while background_processing_active:
            process_trains_sequentially()
            # Wait 5 minutes before next processing cycle
            for i in range(300):  # 300 seconds = 5 minutes
                if not background_processing_active:
                    break
                time.sleep(1)
    
    if not background_processing_active:
        background_processing_active = True
        thread = threading.Thread(target=process_job, daemon=True)
        thread.start()
        print("🔄 Background processing started...")

def stop_background_processing():
    """Stop background processing"""
    global background_processing_active
    background_processing_active = False
    print("⏹️ Background processing stopped...")

# API Endpoints

@app.route('/api/control/start', methods=['POST'])
def start_data_processing():
    """Start data processing manually"""
    try:
        start_background_processing()
        return jsonify({
            'success': True,
            'message': 'Data processing started successfully',
            'status': 'running',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/control/stop', methods=['POST'])
def stop_data_processing():
    """Stop data processing manually"""
    try:
        stop_background_processing()
        return jsonify({
            'success': True,
            'message': 'Data processing stopped successfully',
            'status': 'stopped',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/control/status')
def get_processing_status():
    """Get current processing status"""
    return jsonify({
        'success': True,
        'data': {
            'status': 'running' if background_processing_active else 'stopped',
            'last_processed': datetime.now().isoformat(),
            'trains_processed': len(processed_trains_data),
            'background_processing_active': background_processing_active
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/dashboard/summary')
def get_dashboard_summary():
    """Get dashboard summary"""
    return jsonify({
        'success': True,
        'data': {
            'section_info': {
                'name': 'NDLS → AGC Section',
                'data_source': 'RailRadar Live API',
                'last_updated': datetime.now().isoformat()
            },
            'system_status': 'operational',
            'active_trains': len(processed_trains_data),
            'processing_status': 'running' if background_processing_active else 'stopped'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/trains/table-data')
def get_trains_table_data():
    """Get all trains data for the table - USING GEMINI ANALYSIS"""
    return jsonify({
        'success': True,
        'data': all_trains_table_data,
        'total_trains': len(all_trains_table_data),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/trains/schedule')
def get_trains_schedule():
    """Get all trains schedule and live data - USING LIVE DATA ONLY"""
    schedules = []
    
    for train_number, data in processed_trains_data.items():
        gemini_analysis = data['gemini_analysis']
        table_data = gemini_analysis.get('table_data', {})
        
        schedules.append({
            'train_number': train_number,
            'train_name': table_data.get('name', 'Unknown'),
            'current_location': table_data.get('current_location', 'Unknown'),
            'scheduled_time': table_data.get('scheduled', 'Unknown'),
            'actual_time': table_data.get('actual', 'Unknown'),
            'delay_minutes': table_data.get('delay', 0),
            'status': table_data.get('status', 'Unknown')
        })
    
    return jsonify({
        'success': True,
        'data': schedules,
        'total_trains': len(schedules),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/kpi/current')
def get_current_kpis():
    """Get current KPIs - USING LIVE DATA"""
    if not all_trains_table_data:
        return jsonify({
            'success': True,
            'data': {
                'kpi_data': {
                    'throughput_metrics': {
                        'planned_throughput_trains_per_hour': 0,
                        'actual_throughput_trains_per_hour': 0
                    },
                    'delay_metrics': {
                        'average_delay_minutes': 0,
                        'delayed_trains_count': 0,
                        'on_time_percentage': 0
                    },
                    'utilization_metrics': {
                        'track_utilization_percentage': 0,
                        'platform_utilization_percentage': 0
                    },
                    'punctuality_metrics': {
                        'on_time_percentage': 0,
                        'delayed_percentage': 0
                    }
                }
            },
            'timestamp': datetime.now().isoformat()
        })
    
    total_trains = len(all_trains_table_data)
    delays = [train.get('delay', 0) for train in all_trains_table_data]
    trains_with_delays = sum(1 for delay in delays if delay > 5)
    avg_delay = sum(delays) / len(delays) if delays else 0
    
    # Calculate throughput based on trains near target stations
    near_stations_count = len(gemini_analysis_results.get('trains_near_stations', []))
    actual_throughput = min(near_stations_count / 2, 12)  # Simple calculation
    
    return jsonify({
        'success': True,
        'data': {
            'kpi_data': {
                'throughput_metrics': {
                    'planned_throughput_trains_per_hour': 12.5,
                    'actual_throughput_trains_per_hour': round(actual_throughput, 1)
                },
                'delay_metrics': {
                    'average_delay_minutes': round(avg_delay, 1),
                    'delayed_trains_count': trains_with_delays,
                    'on_time_percentage': round(((total_trains - trains_with_delays) / total_trains * 100), 1)
                },
                'utilization_metrics': {
                    'track_utilization_percentage': min(100, round((near_stations_count / 8) * 100, 1)),
                    'platform_utilization_percentage': min(100, round((near_stations_count / 6) * 100, 1))
                },
                'punctuality_metrics': {
                    'on_time_percentage': round(((total_trains - trains_with_delays) / total_trains * 100), 1),
                    'delayed_percentage': round((trains_with_delays / total_trains * 100), 1)
                }
            }
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/abnormalities')
def get_abnormalities():
    """Get current abnormalities - USING LIVE DATA"""
    abnormalities = []
    
    for train in all_trains_table_data:
        delay = train.get('delay', 0)
        
        if delay > 15: 
            abnormalities.append({
                'train_id': train.get('train_number', 'Unknown'),
                'type': 'delay',
                'description': f'Train {train.get("name", "Unknown")} delayed by {delay} minutes',
                'delay_minutes': delay,
                'location': train.get('current_location', 'Unknown'),
                'detected_at': datetime.now().isoformat(),
                'severity': 'high' if delay > 30 else 'medium'
            })
    
    return jsonify({
        'success': True,
        'data': abnormalities,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/solutions/active')
def get_active_solutions():
    """Get active AI solutions - USING LIVE DATA"""
    solutions = []
    
    for train_number, data in processed_trains_data.items():
        if 'solutions' in data:
            train_solutions = data['solutions'].get('solutions', [])
            for sol in train_solutions:
                solutions.append({
                    'solution_id': f"sol_{train_number}_{int(time.time())}",
                    'train_id': train_number,
                    'way_type': sol.get('solution_type', 'general'),
                    'description': sol.get('description', 'No description'),
                    'priority_score': 8.5 if sol.get('priority') == 'High' else 7.0 if sol.get('priority') == 'Medium' else 5.5,
                    'safety_score': 95,
                    'estimated_impact_minutes': sol.get('expected_impact_minutes', -5),
                    'confidence_level': 'high' if data['solutions'].get('overall_confidence', 0) > 80 else 'medium'
                })
    
    return jsonify({
        'success': True,
        'data': solutions,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/solutions/generate', methods=['POST'])
def generate_solutions():
    """Generate solutions for abnormalities - USING LIVE DATA"""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided',
            'timestamp': datetime.now().isoformat()
        }), 400
    
    train_id = data.get('train_id')
    
    if train_id in processed_trains_data:
        train_data = processed_trains_data[train_id]
        delay_reason = train_data['gemini_analysis'].get('reason', 'Unknown delay')
        
        # Generate solutions using Gemini
        solutions = ask_gemini_generate_solutions(train_data['raw_data'], delay_reason)
        
        if solutions:
            return jsonify({
                'success': True,
                'data': solutions.get('solutions', []),
                'timestamp': datetime.now().isoformat()
            })
    
    return jsonify({
        'success': False,
        'error': 'Could not generate solutions',
        'timestamp': datetime.now().isoformat()
    }), 400

@app.route('/api/trains/near-stations')
def get_trains_near_stations():
    """Get trains near target stations"""
    return jsonify({
        'success': True,
        'data': gemini_analysis_results,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/system/status')
def get_system_status():
    """Get system status"""
    return jsonify({
        'success': True,
        'data': {
            'railradar_api': 'connected' if processed_trains_data else 'disconnected',
            'gemini_ai': 'connected',
            'processing_status': 'running' if background_processing_active else 'stopped',
            'last_processed': datetime.now().isoformat(),
            'trains_processed': len(processed_trains_data),
            'table_data_available': len(all_trains_table_data),
            'background_processing_active': background_processing_active
        },
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    print("🚀 Starting VyuhMitra Backend Server...")
    print("📊 Dashboard available at: http://127.0.0.1:5000")
    print("🔗 API endpoints available at: http://127.0.0.1:5000/api/")
    print("⏸️  Data processing is stopped initially. Use the start button to begin.")
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
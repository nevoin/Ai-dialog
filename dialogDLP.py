import requests
import time
import json
import sys
import re
from colorama import init, Fore, Style

init(autoreset=True)

# ============================================
# COLORS
# ============================================
AI1_COLOR = Fore.GREEN
AI2_COLOR = Fore.CYAN
INFO = Fore.YELLOW
DISCUSSION = Fore.WHITE
ERROR = Fore.RED
PROPOSAL = Fore.MAGENTA

# ============================================
# DEFAULT CONFIGURATION
# ============================================
DEFAULT_PROBLEM = """We are discussing the discrete logarithm problem (DLP) in the context of ECDSA (Elliptic Curve Digital Signature Algorithm).

PROBLEM:
Given an elliptic curve E over finite field F_p, a base point G of order n, and a point Q = k*G (scalar multiplication), find the integer k (the discrete logarithm).

This is the foundation of ECDSA security. Solving DLP would break all elliptic curve cryptography.

Known attacks:
- Baby-step giant-step (O(√n))
- Pollard's rho algorithm (O(√n))
- Pohlig-Hellman (if n factors)
- Quantum Shor's algorithm (polynomial time on quantum computer)

Need to find practical or theoretical approaches to solve DLP for ECDSA curve (secp256k1).

Constraints:
- n is a large prime ~ 2^256
- Curve parameters are standardized
- No known classical polynomial-time solution exists

Discuss existing approaches with your own deep analysis, propose new ideas, explore possible leads, use non-standard approaches.
Classical PC/GPU only - quantum computer does not exist for you!"""

DEFAULT_AI1_ROLE = """You are AI1, a cryptographer and mathematician specializing in elliptic curves and the discrete logarithm problem.

Your style: analytical, rigorous, skeptical. You focus on mathematical proofs, computational complexity, and practical implementations. You critique AI2's ideas and provide counterarguments.

Write ONLY your response."""

DEFAULT_AI2_ROLE = """You are AI2, a cryptographer and algorithm designer focusing on DLP attacks.

Your style: creative, optimistic, implementation-focused. You propose new approaches, hybrid algorithms, or optimizations of existing methods. You counter AI1's skepticism with practical arguments.

Write ONLY your response."""

DEFAULT_AI1_NAME = "AI1 (Cryptographer / Skeptic)"
DEFAULT_AI2_NAME = "AI2 (Algorithm Designer / Optimist)"

# ============================================
# API ENDPOINTS
# ============================================
AI1_URL = "http://localhost:5001"
AI2_URL = "http://localhost:5002"
AI1_GENERATE_URL = f"{AI1_URL}/api/v1/generate"
AI2_GENERATE_URL = f"{AI2_URL}/api/v1/generate"

TIMEOUT = 120
RETRY_COUNT = 3
DELAY_SECONDS = 1

# ============================================
# MODEL AND GPU DETECTION (PURE API)
# ============================================

def get_model_info(base_url: str, port: int) -> dict:
    """Get model and GPU information using only API calls"""
    
    info = {
        'port': port,
        'model_name': 'Unknown',
        'loader': 'Unknown',
        'gpu_memory_gb': 'Unknown',
        'gpu_layers': 'Unknown',
        'gpu_inference': 'Unknown',
        'backend': 'Unknown'
    }
    
    # Try /v1/internal/model/info endpoint
    try:
        response = requests.get(f"{base_url}/v1/internal/model/info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            info['model_name'] = data.get('model_name', 'Unknown')
            info['loader'] = data.get('loader', 'Unknown')
            info['backend'] = data.get('backend', 'Unknown')
    except:
        pass
    
    # If failed, try /v1/models (OpenAI compatible)
    if info['model_name'] == 'Unknown':
        try:
            response = requests.get(f"{base_url}/v1/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    info['model_name'] = data['data'][0].get('id', 'Unknown')
        except:
            pass
    
    # Try to get GPU info from /v1/internal/sysinfo if available
    try:
        response = requests.get(f"{base_url}/v1/internal/sysinfo", timeout=5)
        if response.status_code == 200:
            data = response.json()
            cmd_line = data.get('cmd_line', '')
            
            # Extract GPU memory
            match = re.search(r'--gpu-memory\s+(\d+)', cmd_line)
            if match:
                info['gpu_memory_gb'] = match.group(1)
            
            # Extract GPU layers for llama.cpp
            match = re.search(r'--(?:n-)?gpu-layers\s+(\d+)', cmd_line)
            if match:
                info['gpu_layers'] = match.group(1)
    except:
        pass
    
    # Determine GPU inference status based on loader
    if info['loader'] != 'Unknown':
        loader_lower = info['loader'].lower()
        if loader_lower in ['exllamav2', 'exllamav3', 'exllama', 'transformers', 'autogptq', 'gptq']:
            info['gpu_inference'] = 'Yes (Native GPU)'
        elif loader_lower == 'llama.cpp':
            if info['gpu_layers'] != 'Unknown' and int(info['gpu_layers']) > 0:
                info['gpu_inference'] = f'Yes (llama.cpp, {info["gpu_layers"]} layers on GPU)'
            else:
                info['gpu_inference'] = 'Probably CPU-only (no gpu_layers set)'
        elif loader_lower == 'ctransformers':
            info['gpu_inference'] = 'Yes (CTransformers)'
        else:
            info['gpu_inference'] = f'Unknown loader: {info["loader"]}'
    else:
        info['gpu_inference'] = 'Unable to determine (loader unknown)'
    
    return info

def print_model_info(ai1_info: dict, ai2_info: dict):
    """Print model and GPU information at startup"""
    
    print(INFO + "="*70)
    print(INFO + "MODEL AND GPU ASSIGNMENT")
    print(INFO + "="*70)
    
    # AI1 Info
    print(AI1_COLOR + f"┌─ Port 5001 (AI1)" + Style.RESET_ALL)
    print(AI1_COLOR + f"│  Model: {ai1_info['model_name']}" + Style.RESET_ALL)
    print(AI1_COLOR + f"│  Loader: {ai1_info['loader']}" + Style.RESET_ALL)
    print(AI1_COLOR + f"│  Backend: {ai1_info['backend']}" + Style.RESET_ALL)
    print(AI1_COLOR + f"│  GPU Status: {ai1_info['gpu_inference']}" + Style.RESET_ALL)
    if ai1_info['gpu_memory_gb'] != 'Unknown':
        print(AI1_COLOR + f"│  GPU Memory Limit: {ai1_info['gpu_memory_gb']} GB" + Style.RESET_ALL)
    if ai1_info['gpu_layers'] != 'Unknown':
        print(AI1_COLOR + f"│  GPU Layers: {ai1_info['gpu_layers']}" + Style.RESET_ALL)
    
    print()
    
    # AI2 Info
    print(AI2_COLOR + f"└─ Port 5002 (AI2)" + Style.RESET_ALL)
    print(AI2_COLOR + f"   Model: {ai2_info['model_name']}" + Style.RESET_ALL)
    print(AI2_COLOR + f"   Loader: {ai2_info['loader']}" + Style.RESET_ALL)
    print(AI2_COLOR + f"   Backend: {ai2_info['backend']}" + Style.RESET_ALL)
    print(AI2_COLOR + f"   GPU Status: {ai2_info['gpu_inference']}" + Style.RESET_ALL)
    if ai2_info['gpu_memory_gb'] != 'Unknown':
        print(AI2_COLOR + f"   GPU Memory Limit: {ai2_info['gpu_memory_gb']} GB" + Style.RESET_ALL)
    if ai2_info['gpu_layers'] != 'Unknown':
        print(AI2_COLOR + f"   GPU Layers: {ai2_info['gpu_layers']}" + Style.RESET_ALL)
    
    print(INFO + "="*70 + Style.RESET_ALL)
    print()

# ============================================
# INPUT FUNCTIONS
# ============================================

def get_input(prompt: str, default: str = "") -> str:
    """Get input from user with default value"""
    if default:
        user_input = input(f"{prompt} [default: {default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"{prompt}: ").strip()

def get_int_input(prompt: str, default: int) -> int:
    """Get integer input from user"""
    while True:
        try:
            user_input = input(f"{prompt} [default: {default}]: ").strip()
            if not user_input:
                return default
            value = int(user_input)
            if value > 0:
                return value
            else:
                print(ERROR + "Please enter a positive number" + Style.RESET_ALL)
        except ValueError:
            print(ERROR + "Please enter a valid number" + Style.RESET_ALL)

# ============================================
# AI FUNCTIONS
# ============================================

def ask_ai(ai_name: str, url: str, conversation_history: str, role_prompt: str, max_length: int, temperature: float) -> str:
    """Ask AI to continue discussion"""
    
    system_prompt = f"""{role_prompt}

CONVERSATION SO FAR:
{conversation_history}

Now respond to the last message. Be specific with mathematical details. Write ONLY your response.

{ai_name.split()[0]}:"""

    payload = {
        "prompt": system_prompt,
        "max_length": max_length,
        "temperature": temperature,
        "top_p": 0.95,
        "repetition_penalty": 1.05,
        "stop_sequence": ["\nAI1:", "\nAI2:"]
    }
    
    for attempt in range(RETRY_COUNT):
        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)
            
            if not response.text:
                print(ERROR + f"[{ai_name}] Empty response, attempt {attempt+1}/{RETRY_COUNT}" + Style.RESET_ALL)
                time.sleep(2)
                continue
            
            data = response.json()
            
            if "results" not in data or len(data["results"]) == 0:
                print(ERROR + f"[{ai_name}] No results, attempt {attempt+1}/{RETRY_COUNT}" + Style.RESET_ALL)
                time.sleep(2)
                continue
            
            result = data["results"][0]["text"].strip()
            
            # Clean up - remove prefixes
            result = result.replace("AI1:", "").replace("AI2:", "").strip()
            
            if not result:
                print(ERROR + f"[{ai_name}] Empty result, attempt {attempt+1}/{RETRY_COUNT}" + Style.RESET_ALL)
                time.sleep(2)
                continue
            
            return result
            
        except requests.exceptions.Timeout:
            print(ERROR + f"[{ai_name}] Timeout, attempt {attempt+1}/{RETRY_COUNT}" + Style.RESET_ALL)
            time.sleep(2)
        except Exception as e:
            print(ERROR + f"[{ai_name}] Error: {e}, attempt {attempt+1}/{RETRY_COUNT}" + Style.RESET_ALL)
            time.sleep(2)
    
    return "[AI DID NOT RESPOND]"

# ============================================
# MAIN DISCUSSION LOOP
# ============================================

def run_discussion(problem_description: str, ai1_role: str, ai2_role: str, ai1_name: str, ai2_name: str, max_turns: int, max_length: int, temperature: float):
    
    print(INFO + "="*70)
    print(INFO + "AI DISCUSSION - MILLENNIUM PROBLEM")
    print(INFO + "="*70)
    print(INFO + f"AI1: {ai1_name}")
    print(INFO + f"AI2: {ai2_name}")
    print(INFO + f"Max turns: {max_turns} | Delay: {DELAY_SECONDS}s | Max length: {max_length} | Temperature: {temperature}")
    print(INFO + "="*70 + Style.RESET_ALL)
    print()
    
    print(DISCUSSION + "="*70)
    print(DISCUSSION + "PROBLEM:")
    print(DISCUSSION + "="*70)
    print(problem_description)
    print(DISCUSSION + "="*70 + Style.RESET_ALL)
    print()
    
    print(INFO + "Starting discussion... Press Ctrl+C to stop\n" + Style.RESET_ALL)
    
    conversation_history = problem_description + "\n\n--- DISCUSSION START ---\n"
    
    # AI1 speaks first
    current_ai = 1
    
    for turn in range(1, max_turns + 1):
        print(INFO + f"\n[Turn {turn}/{max_turns}]" + Style.RESET_ALL)
        
        if current_ai == 1:
            print(AI1_COLOR + f"{ai1_name}: " + Style.RESET_ALL, end="")
            response = ask_ai(ai1_name, AI1_GENERATE_URL, conversation_history, ai1_role, max_length, temperature)
            print(AI1_COLOR + response + Style.RESET_ALL)
            conversation_history += f"\n{ai1_name}: {response}\n"
            current_ai = 2
        else:
            print(AI2_COLOR + f"{ai2_name}: " + Style.RESET_ALL, end="")
            response = ask_ai(ai2_name, AI2_GENERATE_URL, conversation_history, ai2_role, max_length, temperature)
            print(AI2_COLOR + response + Style.RESET_ALL)
            conversation_history += f"\n{ai2_name}: {response}\n"
            current_ai = 1
        
        # Check for solution proposal
        if any(word in response.lower() for word in ["solution", "algorithm", "propose", "approach", "method"]):
            print(PROPOSAL + "\n[AI PROPOSED AN APPROACH!]" + Style.RESET_ALL)
        
        if turn < max_turns:
            time.sleep(DELAY_SECONDS)
    
    print(INFO + "\n" + "="*70)
    print(INFO + "DISCUSSION ENDED")
    print(INFO + "="*70 + Style.RESET_ALL)

# ============================================
# MAIN
# ============================================

def main():
    print(INFO + "="*70)
    print(INFO + "AI DISCUSSION CONFIGURATION")
    print(INFO + "="*70 + Style.RESET_ALL)
    print()
    
    # Get model and GPU info at startup
    print(INFO + "Detecting models and GPU assignments..." + Style.RESET_ALL)
    print()
    
    ai1_info = get_model_info(AI1_URL, 5001)
    ai2_info = get_model_info(AI2_URL, 5002)
    
    print_model_info(ai1_info, ai2_info)
    
    # Get configuration from user
    print(INFO + "Enter problem description (press Enter for default DLP problem):" + Style.RESET_ALL)
    problem = get_input("Problem", DEFAULT_PROBLEM)
    
    print(INFO + "\nEnter role for AI1 (press Enter for default):" + Style.RESET_ALL)
    ai1_role = get_input("AI1 role", DEFAULT_AI1_ROLE)
    
    ai1_name = get_input("AI1 display name", DEFAULT_AI1_NAME)
    
    print(INFO + "\nEnter role for AI2 (press Enter for default):" + Style.RESET_ALL)
    ai2_role = get_input("AI2 role", DEFAULT_AI2_ROLE)
    
    ai2_name = get_input("AI2 display name", DEFAULT_AI2_NAME)
    
    max_turns = get_int_input("Max turns", 100)
    
    max_length = get_int_input("Max response length (tokens)", 1000)
    
    print(INFO + "\nTemperature (0.0 = conservative, 1.0 = creative):" + Style.RESET_ALL)
    while True:
        try:
            temp_input = input("Temperature [default: 0.75]: ").strip()
            if not temp_input:
                temperature = 0.75
            else:
                temperature = float(temp_input)
            if 0.0 <= temperature <= 2.0:
                break
            else:
                print(ERROR + "Temperature must be between 0.0 and 2.0" + Style.RESET_ALL)
        except ValueError:
            print(ERROR + "Please enter a valid number" + Style.RESET_ALL)
    
    # Show summary
    print()
    print(INFO + "="*70)
    print(INFO + "CONFIGURATION SUMMARY")
    print(INFO + "="*70)
    print(INFO + f"AI1: {ai1_name}")
    print(INFO + f"AI2: {ai2_name}")
    print(INFO + f"Max turns: {max_turns}")
    print(INFO + f"Max length: {max_length}")
    print(INFO + f"Temperature: {temperature}")
    print(INFO + "="*70 + Style.RESET_ALL)
    print()
    
    confirm = input(INFO + "Start discussion? (y/n): " + Style.RESET_ALL).strip().lower()
    if confirm != 'y':
        print(INFO + "Cancelled." + Style.RESET_ALL)
        return
    
    try:
        run_discussion(problem, ai1_role, ai2_role, ai1_name, ai2_name, max_turns, max_length, temperature)
    except KeyboardInterrupt:
        print(INFO + "\n\nDiscussion interrupted by user" + Style.RESET_ALL)
    except Exception as e:
        print(ERROR + f"Unexpected error: {e}" + Style.RESET_ALL)

if __name__ == "__main__":
    main()

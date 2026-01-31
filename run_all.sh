#!/bin/bash

# SPECTRA Framework - Automation Runner
# Author: MehranTurk (M.T)

echo " [!] Starting SPECTRA Infrastructure..."

# 1. Start PostgreSQL (Required for Metasploit)
echo " [*] Checking PostgreSQL service..."
sudo service postgresql start

# 2. Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null
then
    echo " [!] Ollama is not running. Starting Ollama in background..."
    ollama serve &
    sleep 5
else
    echo " [+] Ollama service is active."
fi

# 3. Start Metasploit RPC Server
# Using the password defined in our core/rpc_client.py
echo " [*] Starting Metasploit RPC Server on port 55553..."
msfrpcd -P mehran123 -u msf -S false &
sleep 10 # Wait for RPC to fully initialize

# 4. Check requirements
echo " [*] Checking Python dependencies..."
pip install -r requirements.txt --quiet

# 5. Launch SPECTRA Main Core
echo " [+] Infrastructure is ready. Launching SPECTRA..."
echo " --------------------------------------------------"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo " Usage: ./run_all.sh <TARGET_IP> <YOUR_LHOST>"
    # Keep the RPC running for manual use if needed
else
    python3 main.py "$1" "$2"
fi
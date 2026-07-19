import os

file_path = r'D:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\client\05_SIAP_DISTRIBUSI\PC_HEALTH_AGENT.py'
out_path = r'D:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\update_line.txt'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(out_path, 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines, 1):
        if 'check_for_updates' in line:
            out.write(f"{i}: {line.strip()}\n")

print("SUCCESS")

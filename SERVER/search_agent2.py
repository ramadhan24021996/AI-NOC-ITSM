import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

keywords = ["realtime", "Failed realtime send"]

for root, dirs, files in os.walk("D:\\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for kw in keywords:
                    if kw.lower() in content.lower():
                        # print file and line numbers
                        lines = content.splitlines()
                        for idx, line in enumerate(lines):
                            if kw.lower() in line.lower():
                                print(f"{path} Line {idx+1}: {line.strip()}")
            except Exception as e:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

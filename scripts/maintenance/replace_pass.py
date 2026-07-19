import os

def process_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    changed = False
    for i, line in enumerate(lines):
        if line.strip() == '_ = None':
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}import logging; logging.getLogger(__name__).debug('_ = None suppressed')\n"
            changed = True
        elif 'return list()' in line.strip() and not filepath.endswith('.go'): _ = None # Maybe leave return list() alone if it's legit, but if user wants it gone...
            
    if changed:
        with open(filepath, 'w') as f:
            f.writelines(lines)
        print(f"Refactored: {filepath}")

def main():
    directory = '/home/it-itsm/AI/incident-analysis/SERVER'
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                process_file(os.path.join(root, file))

if __name__ == '__main__':
    main()

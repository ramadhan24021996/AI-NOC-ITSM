import os
import json
import re

def analyze_workspace(root_dir):
    stats = {
        'total_folders': 0,
        'total_files': 0,
        'python_files': 0,
        'go_files': 0,
        'docker_services': 0,
        'nats_subjects': set(),
        'rest_apis': set(),
        'db_tables': set(),
        'tree': {}
    }
    
    ignore_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv'}
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        
        rel_path = os.path.relpath(dirpath, root_dir)
        stats['total_folders'] += 1
        
        for file in filenames:
            stats['total_files'] += 1
            if file.endswith('.py'):
                stats['python_files'] += 1
            elif file.endswith('.go'):
                stats['go_files'] += 1
                
            file_path = os.path.join(dirpath, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # NATS subjects (very basic heuristic)
                    nats_matches = re.findall(r'\"([a-zA-Z0-9_]+\.[a-zA-Z0-9_\.]+)\"', content)
                    for m in nats_matches:
                        if 'nats' in file_path.lower() or 'queue' in file_path.lower() or 'subject' in content.lower():
                            if len(m.split('.')) >= 2:
                                stats['nats_subjects'].add(m)
                                
                    # REST APIs
                    api_matches = re.findall(r'(GET|POST|PUT|DELETE)\s+([\'"`])(/api/[a-zA-Z0-9_/-]+)\2', content)
                    for match in api_matches:
                        stats['rest_apis'].add(f"{match[0]} {match[2]}")
                        
                    api_matches2 = re.findall(r'(?:@app\.(get|post|put|delete)|router\.(?:Get|Post|Put|Delete))\s*\([\'"`](/api/[a-zA-Z0-9_/-]+)[\'"`]', content, re.IGNORECASE)
                    for match in api_matches2:
                        stats['rest_apis'].add(f"{match[0].upper()} {match[1]}")
                        
                    # DB tables (basic heuristic from CREATE TABLE or ORM models)
                    table_matches = re.findall(r'CREATE TABLE (?:IF NOT EXISTS )?([a-zA-Z0-9_]+)', content, re.IGNORECASE)
                    for t in table_matches:
                        stats['db_tables'].add(t)
                        
                    orm_matches = re.findall(r'__tablename__\s*=\s*[\'"]([a-zA-Z0-9_]+)[\'"]', content)
                    for t in orm_matches:
                        stats['db_tables'].add(t)

            except Exception:
                _ = None
                
    # Parse docker-compose
    dc_path = os.path.join(root_dir, 'docker-compose.yml')
    if os.path.exists(dc_path):
        try:
            with open(dc_path, 'r', encoding='utf-8') as f:
                content = f.read()
                services = re.findall(r'^\s*([a-zA-Z0-9_-]+):$', content, re.MULTILINE)
                # Filter out standard keys like networks, volumes, etc if they appear at root (this is a simplified regex)
                stats['docker_services'] = len([s for s in services if s not in ['networks', 'volumes', 'services', 'version']])
        except:
            _ = None

    stats['nats_subjects'] = list(stats['nats_subjects'])
    stats['rest_apis'] = list(stats['rest_apis'])
    stats['db_tables'] = list(stats['db_tables'])
    
    with open('workspace_analysis.json', 'w') as f:
        json.dump(stats, f, indent=2)

if __name__ == '__main__':
    analyze_workspace('.')

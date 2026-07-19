import os

def generate_tree(dir_path, level=0, max_level=3, ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = {'.git', 'venv', 'node_modules', '__pycache__'}
    
    if level > max_level:
        return ""
    
    tree_str = ""
    try:
        items = sorted(os.listdir(dir_path))
    except PermissionError:
        return ""
        
    for item in items:
        if item in ignore_dirs:
            continue
            
        full_path = os.path.join(dir_path, item)
        indent = "│   " * level
        
        if os.path.isdir(full_path):
            tree_str += f"{indent}├── {item}/\n"
            tree_str += generate_tree(full_path, level + 1, max_level, ignore_dirs)
        else:
            tree_str += f"{indent}├── {item}\n"
            
    return tree_str

with open("folder_tree.txt", "w") as f:
    f.write("incident-analysis/\n")
    f.write(generate_tree(".", max_level=2))

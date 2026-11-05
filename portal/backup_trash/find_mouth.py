import sys

vertices = []
with open('portal/static/models/WaltHead.obj', 'r') as f:
    for line in f:
        if line.startswith('v '):
            parts = line.strip().split()
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))

# scale by 6
vertices = [(x*6, y*6, z*6) for x, y, z in vertices]

min_y = min(v[1] for v in vertices)
max_y = max(v[1] for v in vertices)
max_z = max(v[2] for v in vertices)

print(f"Scaled Min Y: {min_y}, Max Y: {max_y}, Max Z: {max_z}")

# The front of the face is near max_z
front_vertices = [v for v in vertices if v[2] > max_z - 30]

# Find the nose (highest Z in the middle of Y)
nose_candidates = [v for v in front_vertices if 50 < v[1] < 150]
if nose_candidates:
    nose = max(nose_candidates, key=lambda v: v[2])
    print(f"Approx Nose: {nose}")
else:
    print("Nose candidates not found")

# Mouth should be slightly below nose

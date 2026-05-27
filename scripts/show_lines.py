import sys
p = r'c:\Users\rocha\OneDrive\Escritorio\Sistema-POS-main\reports\templates\reports\advanced_reports.html'
start = int(sys.argv[1]) if len(sys.argv)>1 else 900
end = int(sys.argv[2]) if len(sys.argv)>2 else start+40
with open(p, encoding='utf-8') as f:
    lines = f.readlines()
for i in range(start-1, min(end, len(lines))):
    print(f"{i+1:4}: {lines[i].rstrip()}")

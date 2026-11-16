"""Compara dois out/orcamento.json (antes/depois da migração para config/) campo a campo.
Uso: python projects/fernanda-sertorio/comparar_orcamentos.py antes.json depois.json
Classifica cada diferença: NUMERICA (valores numéricos/booleanos/estrutura) ou TEXTO (apenas strings). Exit 1 se houver diferença NUMERICA."""
import json, sys


def diff(a, b, path=""):
    out = []
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool)):
        return [(path, a, b)]
    if isinstance(a, dict):
        for k in a.keys() | b.keys():
            if k not in a or k not in b: out.append((f"{path}/{k}", a.get(k, "<ausente>"), b.get(k, "<ausente>")))
            else: out += diff(a[k], b[k], f"{path}/{k}")
        if list(a.keys()) != list(b.keys()) and not out: out.append((path + " (ordem das chaves)", list(a.keys()), list(b.keys())))
    elif isinstance(a, list):
        if len(a) != len(b): return [(path + " (tamanho)", len(a), len(b))]
        for i, (x, y) in enumerate(zip(a, b)): out += diff(x, y, f"{path}[{i}]")
    elif a != b: out.append((path, a, b))
    return out


def contagens(o):
    p = o["project"]; r = o["report"]
    return {"pecas_linhas": len(p["pieces"]), "pecas_unidades": sum(x["qty"] for x in p["pieces"]), "materiais": len(p["materials"]), "fitas": len(p["edgeBands"]), "ferragens": len(p["hardware"]),
            "extras": len(p["extras"]), "planos": len(r["plans"]), "chapas": sum(len(pl["sheets"]) for pl in r["plans"]), "issues": len(r["issues"]), "orcamento": r["budget"]}


if __name__ == "__main__":
    a, b = (json.load(open(f)) for f in sys.argv[1:3])
    d = diff(a, b); num = [x for x in d if not (isinstance(x[1], str) and isinstance(x[2], str))]; txt = [x for x in d if x not in num]
    print("campos folha comparados:", sum(1 for _ in json.dumps(a).split(",")), "(aprox.)"); print("antes :", contagens(a)); print("depois:", contagens(b))
    print(f"diferenças NUMÉRICAS/estruturais: {len(num)}"); [print("  ", x) for x in num[:50]]
    print(f"diferenças só de TEXTO: {len(txt)}"); [print("  ", x[0], "|", repr(x[1])[:70], "->", repr(x[2])[:70]) for x in txt[:40]]
    sys.exit(1 if num else 0)

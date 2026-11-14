"""CLI da leitura técnica.

  python -m ingest.technical analisar arquivo.pdf saida.json [--enfileirar]
  python -m ingest.technical decidir registro.jsonl resultado.json --medida ID --decisao aprovado|rejeitado --revisor "Nome" [--obs "..."] [--valor "..."]
  python -m ingest.technical aplicar resultado.json registro.jsonl saida.json
"""
import argparse, json, sys

from .model import Resultado
from .pipeline import analisar_pdf
from .revisao import RegistroAdulterado, RegistroRevisoes, aplicar_revisoes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ingest.technical"); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analisar"); a.add_argument("pdf"); a.add_argument("saida"); a.add_argument("--enfileirar", action="store_true")
    d = sub.add_parser("decidir"); d.add_argument("registro"); d.add_argument("resultado"); d.add_argument("--medida", required=True)
    d.add_argument("--decisao", required=True, choices=["aprovado", "rejeitado"]); d.add_argument("--revisor", required=True); d.add_argument("--obs"); d.add_argument("--valor")
    p = sub.add_parser("aplicar"); p.add_argument("resultado"); p.add_argument("registro"); p.add_argument("saida")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "analisar":
            r = analisar_pdf(args.pdf, enfileirar=args.enfileirar)
            open(args.saida, "w", encoding="utf-8").write(r.model_dump_json(indent=1))
            print(f"{r.resumo.total} medidas {r.resumo.por_estado} -> {args.saida}")
        elif args.cmd == "decidir":
            r = Resultado.model_validate_json(open(args.resultado, encoding="utf-8").read())
            m = next((x for x in r.medidas if x.id == args.medida), None)
            if m is None:
                print(f"medida '{args.medida}' não existe neste resultado", file=sys.stderr); return 2
            e = RegistroRevisoes(args.registro).registrar(medida=m, decisao=args.decisao, revisor=args.revisor, observacao=args.obs, valor_confirmado=args.valor)
            print(f"decisão #{e['seq']} registrada ({args.decisao} por {e['revisor']})")
        else:
            r = Resultado.model_validate_json(open(args.resultado, encoding="utf-8").read())
            rel = aplicar_revisoes(r, RegistroRevisoes(args.registro))
            open(args.saida, "w", encoding="utf-8").write(r.model_dump_json(indent=1))
            print(json.dumps({k: len(v) for k, v in rel.items()}), "->", args.saida)
    except RegistroAdulterado as e:
        print(f"REGISTRO ADULTERADO: {e}", file=sys.stderr); return 3
    except ValueError as e:                                   # inclui ValidationError (ex.: revisor não humano)
        print(f"ENTRADA INVÁLIDA: {str(e).splitlines()[0]}", file=sys.stderr); return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())

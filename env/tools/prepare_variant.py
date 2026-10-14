"""Prepare one trusted task configuration for the isolated MCP collector."""
import argparse
from pathlib import Path
from hgj.codec import canonical
from tools.variant_controls import configuration, VARIANTS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',choices=VARIANTS,required=True)
    parser.add_argument('--removal-source',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    config=configuration(args.variant,with_removal_policy=True,removal_source_dir=args.removal_source)
    with Path(args.out).open('xb') as stream:
        stream.write(canonical(config))


if __name__=='__main__':
    main()

#!/usr/bin/env python3

import pandas as pd
import argparse
import os
import sys

parser = argparse.ArgumentParser(description='Dump xls(x) files tab(s) to .tsv files, to the (default output) path')

parser.add_argument('inputfiles', type=str, nargs='*', help='name of xls-file to process')

tabgroup = parser.add_mutually_exclusive_group()

tabgroup.add_argument('--tabnames', dest='tabnames', action='store_true',
                    default=False, help='dump name of tabs')

tabgroup.add_argument('--tab', type=str, dest='tab', default=None,
                    help='name of tab to process')

tabgroup.add_argument('--ffill', dest='ffill', action='store_true',
                      default=False, help='forward fill missing values')

filegroup = parser.add_mutually_exclusive_group()

filegroup.add_argument('--path', dest='path', type=str, default='output',
                    help='output directory file')

filegroup.add_argument('--stdout', dest='stdout', action='store_true',
                    default=False, help='dump a tab to stdout')

parser.add_argument('--sourcename', dest='sourcename', action='store_true',
                    default=False, help='prepend filename to output tab file')

args = parser.parse_args()

path = args.path

if not os.path.exists(path):
    os.makedirs(path)

if args.tabnames:
    for filename in args.inputfiles:
        if len(args.inputfiles) > 1:
            print(filename)
        df = pd.read_excel(filename, None)
        print('\t'.join(df.keys()))
    sys.exit(0)

for filename in args.inputfiles:    
    if args.tab:
        tab = args.tab
        filebase = ''
        if args.sourcename:
            filebase = filename + ':'
            if '.' in filename:
                filebase = filename.rsplit('.', 1)[0] + ':'
        try:
            df = pd.read_excel(filename, tab)
            if args.ffill:
                df = df.fillna(method='ffill')
            if args.stdout:
                df.to_csv(sys.stdout, index=False, sep='\t')     
            else:
                df.to_csv('{}/{}{}.tsv'.format(path, filebase, tab), index=False, sep='\t')
        except KeyError:
            pass
    else:
        df = pd.read_excel(filename, None)
        filebase = ''
        if args.sourcename:
            filebase = filename + ':'
            if '.' in filename:
                filebase = filename.rsplit('.', 1)[0] + ':'
        for tab in df.keys():
            if args.ffill:
                df[tab] = df[tab].fillna(method='ffill')
            df[tab].to_csv('{}/{}{}.tsv'.format(path, filebase, tab), index=False, sep='\t')


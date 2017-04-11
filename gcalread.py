from optparse import OptionParser # in Python 2.7 optparse will be replaced by argparse
from os.path import realpath, dirname, join
import json

# Read configuration defined in a JSON file
GCALFEED_CONFIG = 'config.json'
script_real_path = dirname(realpath(__file__))
infile = join(script_real_path, GCALFEED_CONFIG)
with open(infile) as f:
    config = json.load(f)

infile = join(script_real_path, config['outfile'])

data = []

with open(infile) as f:
    lines = f.readlines()

for line in lines:
    data.append(tuple(line.split('\t')))

list.sort(data, key=lambda data: data[0])

parser = OptionParser(description='Print column of data from ' + infile)
parser.add_option('-c', '--col', type='int', action='store', default=1, help='column(s) to print')

(options, args) = parser.parse_args()

if options.col >= len(data[0]):
    parser.error("-c option maximum value is %s" % (len(data[0])-1,))

for entry in data:
    print (entry[options.col].strip())

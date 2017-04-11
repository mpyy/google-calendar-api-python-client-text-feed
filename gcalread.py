from optparse import OptionParser # in Python 2.7 optparse will be replaced by argparse
import os.path

GCALFEED_INFILE = 'gcal_feeds.out'
script_real_path = dirname(realpath(__file__))
infile = join(script_real_path, GCALFEED_INFILE)

data = []

with open(infile) as f:
    lines = f.readlines()

for line in lines:
    data.append(tuple(line.split('\t')))

list.sort(data, key=lambda data: data[0])

parser = OptionParser(description='Print column of data from ' + GCALFEED_INFILE)
parser.add_option('-c', '--col', type='int', action='store', default=1, help='column(s) to print')

(options, args) = parser.parse_args()

if options.col >= len(data[0]):
    parser.error("-c option maximum value is %s" % (len(data[0])-1,))

for entry in data:
    print (entry[options.col].strip())

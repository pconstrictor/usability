#! /usr/bin/python3

''' This Python 3.x module provides a class for applying regular expressions. 

If run as a script, it will take an input file (plain text) and a set of regexes saved 
as a text file (a sample file is provided) and will output a converted text file. You 
can specify these files via the command line, or else just name your input file to match the 
provided default.
If you use it often, you can 'install' it by adding the SFMUtils folder to your Windows PATH. 
Appending ";.PY;.PYW" to the PATHEXT variable will allow you to leave off the ".py" . More details here:
http://linguisticsoftware.wordpress.com/2012/11/23/running-python-scripts-conveniently-under-windows/

Sample command-line calls (the first just displays help, the second converts 
input.txt to output.txt, overwriting it if it's there):
python ApplyRE.py -h
python ApplyRE.py -o input.txt output.txt

In Windows, you may want to create a batch file that you can easily double-click to run this. But don't name it ApplyRE.bat
Example 1:
python ApplyRE.py -o
pause
Example 2:
C:\Python32\python.exe ApplyRE.py "C:\temp\myfile.txt" "C:\temp\out.txt" -o
pause

'''

import re, argparse, os, io

# CONSTANTS:

STOP_IGNORING = '}}'
RECORD_MARKER = 'lx'
REGEX_DESC = '##'
BROAD = 'broad'  
NARROW = 'sfmval'
NARROW_NON_SPECIFIC = 'sfmval'  
DISABLED = 'disable' # just needs to start with this; e.g. "DISABLED" is fine--better, actually.

INFILE='lexicon.txt'
OUTFILE='lexicon-out.tmp.txt'
REGEXFILE='ApplyRE.regex.txt'

import unicodedata
def ascii(s):
    '''Given a (unicode) string, force it to use ASCII characters only. E.g. this is safe to print to a Windows console.
    
    The returned string may have LOST SOME INFORMATION, in which case a tilde will be prefixed to it.'''
    s2 = unicodedata.normalize('NFKD', s)
    b = s2.encode('ASCII', 'replace')
    s3 = b.decode()
    if s3 != s:
        s3 = "~" + s3
    return s3

	
class RegExpression:
    '''A simple class that compiles a regular expression's find string and stores it along with its other data
    
    Initialization parameters:
    - a find pattern, a replace pattern, and a list of fields it applies to
    - optional: re flags
    Tested with Python 3.2 on Microsoft Windows
    Author: Jonathan Coombs <jonathan_coombs@sil.org>
    '''

    def __init__(self, find_this, replace_with, fields, flags = re.LOCALE | re.MULTILINE | re.UNICODE):  #removed first part: re.DOTALL | 
        self._find = re.compile(find_this,flags)
        self._findstr = find_this #just for visual reference
        self._replace = replace_with
        
        self._fields = list()
        f = fields.lower()
        if f.startswith(BROAD):
            self.narrow = False  # Broad; should apply to the whole file.
            self._narrow_specific = False
        elif f.startswith(NARROW + ':') or f.startswith(NARROW + ' '):
            self.narrow = True
            self._narrow_specific = True
            self._fields = fields.split(' ')[1:]
        elif f.startswith(NARROW_NON_SPECIFIC):
            self.narrow = True
            self._narrow_specific = False  # Narrow, but no specific SFM fields were specified
        else:
            raise Exception('Invalid regex scope label: {}'.format(fields))


    def apply(self, data):
        '''Apply a compiled regular expression broadly (to all of the data from the file).
        
        Not specific to SFM files; can be used with any text file.
        '''
        if self.narrow: 
            raise Exception('This regex is not intended to be applied broadly to the whole file.')
        f, rw = self._find, self._replace
        #TODO: Is there a better way to do the following? Presumably this hogs memory, but maybe that's necessary. It performs very fast.
        try:
            ret = f.subn(rw, data, 0)
        except:
            print('Error applying regex: \n{}\n{}'.format(self._findstr, rw))
            raise
        
        return ret

    def apply_narrowly(self, record):
        '''Apply self's regular expression to the data portions of the supplied SFM record. SFM markers will NOT be affected.
        
        Scope: if specific fields were listed for this regex, perform the replace on only those fields' contents 
        '''

        if not self.narrow: 
            raise Exception('This regex is intended to be applied broadly to the whole file, NOT narrowly.')
        
        i, count = 0, 0
        
        for mkr, field_data in record:
            #apply the regular expression to this field's data area.
            if (not self._narrow_specific) or (mkr in self._fields):
                field_data, c = self._find.subn(self._replace, field_data, 0)
                if c:
                    record[i] = [mkr, field_data]  #update that line within the stored record
                    count += c
            i += 1
        return record, count

from time import clock
class RoughTimer:
    ''' A class for measuring how well the find/replace operations perform. '''
    def __init__(self):
        self.started = clock()       
    def just_elapsed(self):
        tmp = clock()
        diff = tmp - self.started
        self.started = tmp 
        return '{} ms'.format(diff*1000)

def get_args():
    ''' Parse any command line arguments (all are optional). '''
    parser = argparse.ArgumentParser(description='Apply regular expressions to a file.')
    tmp = 'the input file (default: {})'.format(INFILE)
    parser.add_argument('infile', default=INFILE, nargs='?', help=tmp)
    tmp = 'the output file to save to (def: {})'.format(OUTFILE)
    parser.add_argument('outfile', default=OUTFILE, nargs='?', help=tmp)
    tmp = 'a config file of regular expressions (def: {})'.format(REGEXFILE)
    parser.add_argument('regexfile', default=REGEXFILE, nargs='?', help=tmp)
    parser.add_argument('-o', '--overwrite', dest='overwr', default=False, action='store_const', const=True, 
                        help='overwrite the output file, if it already exists')
    return vars(parser.parse_args())

def get_regexes(fname):
    ''' Load the regexes from the config file
    
    This simple parser ignores the initial curly-bracketed comments, loads the record marker setting (required but can be empty),
    and then loops:
    - ignore any blank or whitespace-only lines
    - read and drop one or more description lines beginning with ##; raise an error on anything else
    - read exactly one line indicating scope
    - read exactly one line indicating what to find
    - read exactly one line indicating what to replace it with
    - repeat
    '''
    regexes, i = [], 0
    with open(fname, encoding='utf-8') as config:
        data = True
        while data: 
            data = config.readline()
            i += 1
            if data and data.startswith(STOP_IGNORING): 
                break #ignore initial comments through to the }}
            
        config.readline() #toss one blank line
        record_marker = RECORD_MARKER
        tmp = config.readline()
        if ':' in tmp: 
            record_marker = tmp.split(':')[-1].strip() #grab the value to the right of the colon
        i += 3
        
        data = config.readlines()
        find_this, replace_with, scope, state = None, None, None, 0  #have not yet found the description line(s)
        for line in data:
            i += 1
            line = line.rstrip("\r\n") #not a general rstrip() because whitespace matters in states 2-3
            if state == 0: #ready for next regex
                line = line.rstrip()
                if not line:
                    pass
                elif line.startswith(REGEX_DESC):
                    state = 1
                else:
                    raise Exception('Config ERROR near line {}: Each regex needs to begin with at least one description line beginning with {}.'.format(i, REGEX_DESC))
            elif state == 1: #ready for another description line or for the scope line
                if not line.startswith(REGEX_DESC):
#                    scope = line.split(' ') #scope is a list of field names (or a special code)
                    scope = line
                    state = 2
            elif state == 2: #on the find_this line
                find_this = line
                state = 3
            elif state == 3: #on the replace_this line
                replace_with = line
#                if scope[0].startswith(DISABLED): #if disabled
                if scope.lower().startswith(DISABLED.lower()): #if disabled
                    pass
                else:
                    regexes.append(RegExpression(find_this, replace_with, scope))
#                    print('find: {}\n replace: {}\n scope: {}\n'.format(find_this, replace_with, scope)) #fails in a Windows command console if there are special characters
                find_this, replace_with, scope = None, None, None  # reset for next regex
                state = 0
    if not state == 0: 
        raise Exception('Config ERROR near line {}: Incomplete set of info for the regular expression at the end of the regex file.'.format(i))
    if len(regexes) < 1:
        raise Exception('Config ERROR: Please close the initial comments with a line beginning with {} and after that provide at least one enabled regular expression.'.format(STOP_IGNORING))
    return record_marker, regexes 
        
def print_joined(caption, record):
    '''Put a parsed SFM record back into string form.
    '''
    print(caption)
    tmp = ""
    for field in record:
        #join everything back into a string
        tmp += "\\" + field[0]
        if not field[1].startswith("\n"): tmp += " "
        tmp += field[1]
    print(tmp.encode())

def run_sample(regexes):
    print('Import ERROR. Cannot import SFM Tools; aborting and demoing narrow regexes on a canned sample instead.')
    record = [['lx', 'bleeh\n\n'],
              ['de', 'foo eeh\n'],
              ['se', 'yeeda\n'],
              ['de', 'beeh\n']]
    print_joined('BEFORE:', record)
    for regex in regexes:
        if regex.narrow:
            record, _count = regex.apply_narrowly(record)
    print_joined('AFTER:', record)
    

def execute(args):    
    print('Running ApplyRE.py v0.2')
    fnamein = args['infile']
    fnameout = args['outfile']
    fnameregex = args['regexfile']
    overwrite = args['overwr']
    record_marker, regexes = get_regexes(fnameregex)
    some_narrow = False
    for regex in regexes:
        if regex.narrow: some_narrow = True
    
    modcount=0
    if not overwrite and os.path.exists(fnameout):
        print("Output file already exists! Aborted.")
        t = RoughTimer()
    else:
        with open(fnamein, encoding='utf-8') as infile:
            data = infile.read() #read the whole data file into memory (even though SFMTools doesn't require this)
        t = RoughTimer()
       
        if some_narrow:
            print("Applying regular expressions (some are narrow)...")
        else:
            print("Applying {} regular expressions (all are broad) ...".format(len(regexes)))

        if some_narrow:
            try:
                import SFMTools as sfm  #although NLTK has similar functionality too
            except ImportError:
                run_sample(regexes)  #just play with a pre-parsed sample
                raise Exception('Aborted.')
                
        i=0
        modcounttotal = 0
        for regex in regexes:
            i+=1
            modcount = 0 
            print('  just took: {}'.format(t.just_elapsed()))
            #msg = 'applying regex {} of {}'.format(i, len(regexes))
            msg = 'applying regex {} of {}: \n    {}\n    {}'.format(i, len(regexes), regex._findstr, regex._replace)
            msg = ascii(msg)
            data_out = io.StringIO('') #initialize an empty stream object

            if not regex.narrow:
                print('Broadly', msg)
                data, count = regex.apply(data)
                modcount += count

            else:
            #TODO: POOR PERFORMANCE! the section below needs to be optimized, probably in the apply_narrowly() code
            # It seems inefficient to process the header and parse the file into a list every time, but that seems necessary.
            # (Regexes could change record boundaries, delete records, etc., so it's better to reload.) And I doubt that's
            # the main problem, since the script is slow even when only a single (narrow) regex is applied.
                print('Narrowly', msg)
                sfm_records = sfm.SFMRecordReader(data, record_marker)
                data_out.write(sfm_records.header) 
                for sfm_record in sfm_records:
                    L = sfm_record.as_lists() #returns a pointer to a MODIFIABLE list object 
                    L, count = regex.apply_narrowly(L) #modifies the list
                    modcount += count
                    #TODO: Consider caching the following as it is, if the next regex is 'narrow' too, so as to not have to reparse the SFM file/string
                    data_out.write(sfm_record.as_string()) 
                    data = data_out.getvalue() 
            print('  made {} changes'.format(modcount))

            modcounttotal += modcount

        with open(fnameout, mode='w', encoding='utf-8') as outfile:
                outfile.write(data)
    print('just took: {}'.format(t.just_elapsed()))
    print("Done. A total of {} modifications were made".format(modcounttotal))

if __name__ == '__main__':
    '''Take the input file, apply all the regular-expression substitutions to it, and save to the output file.
    '''

    args = get_args() #get args as a dictionary
    execute(args)
  

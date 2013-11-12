#
#
# Multipopulation script calls the selection
# pipeline for each population that we need
# to do then zips up and runs a script to p# each of the cross population statistics once
# it has all finished.
# institution: University of Otago
# author: James Boocock
#
#
# requires that the selection pipeline is 
# installed.
#

from collections import OrderedDict
import sys
import os
import subprocess
from optparse import OptionParser
import ConfigParser
import logging
from .environment import set_environment
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)


SUBPROCESS_FAILED_EXIT = 10
CANNOT_FIND_EXECUTABLE = 20
CANNOT_FIND_CONFIG = 30



# generate RSB after we have calculated ihs

def rsb(config,options,populations):
    rscript = config['Rscript']['rscript_executable']
    generate_rsb =config['Rscript']['generate_rsb']
    directory = 'rsb'
    if not os.path.exists(directory):
        os.mkdir(directory)
    pops = list(populations.keys())
    orig_dir = os.getcwd()
    os.chdir(directory)
    for i in range(0,len(pops)-1):
        cmd=[]
        pop1 = pops[i]
        cmd.append(rscript)
        pop1_ihh_file = os.path.join(orig_dir,pop1,'results', pop1 + 'chr' +options.chromosome + '.ihh')
        cmd.extend([generate_rsb,'--pop1',pop1,'--pop1file',pop1_ihh_file])
        for j in range(i+1,len(pops)):
            tmp_cmd=[]
            tmp_cmd.extend(cmd)
            pop2=pops[j] 
            pop2_ihh_file = os.path.join(orig_dir,pop2,'results', pop2 + 'chr' +options.chromosome + '.ihh')
            tmp_cmd.extend(['--pop2',pop2,'--pop2file',pop2_ihh_file])
            tmp_cmd.extend(['--chr',options.chromosome]) 
            run_subprocess(tmp_cmd,'rsb_generation') 
             



def get_populations(populations):
    pops = {}
    for pop in populations:
        with open(pop, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if ( i == 0 ):
                    pop_name = line
                    pops[pop_name]=[]
                else:
                    pops[pop_name].append(line)
    return pops
def parse_config(options):
    config = ConfigParser.ConfigParser()
    config.read(options.config_file)
    config_parsed = {}
    logger.debug(config.sections())
    for section in config.sections():
        logger.debug(section)
        opts = config.options(section)
        config_parsed[section] = {}
        for op in opts:
            logger.debug(op)
            try:
                config_parsed[section][op] = config.get(section,op)
            except:
                logger.info("exception on {0}".format(op))
                config_parsed[section][op] = None
    return config_parsed

def run_subprocess(command,tool,stdout=None):  
        try:
            if(stdout is None):
                exit_code = subprocess.Popen(command,stderr=subprocess.PIPE,stdout=subprocess.PIPE) 
            else:
                exit_code = subprocess.Popen(command,stdout=stdout,stderr=subprocess.PIPE)
        except:
            logger.error(tool + " failed to run " + ' '.join(command))
            sys.exit(SUBPROCESS_FAILED_EXIT)   
        exit_code.wait()
        if(exit_code.returncode != 0): 
            sys.exit(SUBPROCESS_FAILED_EXIT)   
        while True:
            line = exit_code.stdout.readline()
            if not line:
                break
            logger.info(tool + " STDOUT: " +line)
        while True:
            line = exit_code.stderr.readline()
            if not line:
                break
            logger.info(tool +" STDERR: " + line)
        logger.error("Finished tool " + tool)


def check_executables_and_scripts_exist(options,config): 
        executables=['vcf-subset','selection_pipeline']
        if(which(config['vcftools']['vcf_subset_executable'],'vcf-subset')is None):
            return False
        if(which(config['selection_pipeline']['selection_pipeline_executable'],'selection_pipeline') is None):
            return False
        return True


# Copied from standard run to check whether the programs exist. So much copy pasta.

def is_script(fpath):
    return os.path.isfile(fpath)
def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
#Stolen code from 
#http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def which(program,program_name):
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
        elif (is_script(program)):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    logger.error(program_name +" path = " + fpath+" not locatable path or in the directory specified in your config file ")
    return None

def subset_vcf(vcf_input,config,populations):
    vcf_outputs = []
    for key, value in populations.items():
        cmd = []
        vcf_output = open(key + '.vcf','w')
        population = key
        comma_list_ids = ','.join(value)
        vcf_subset_executable=config['vcftools']['vcf_subset_executable']
        cmd.append(vcf_subset_executable)
        cmd.extend(['-f','-c',comma_list_ids,vcf_input])
        run_subprocess(cmd,'vcf-merge',stdout=vcf_output)
        vcf_outputs.append(key + '.vcf')
        vcf_output.close()
    return vcf_outputs 

def run_selection_pipeline(output_vcfs,options,populations,config):
    orig_dir = os.getcwd()
    if(options.extra_args is not None):
        extra_args=options.extra_args
    else:
        extra_args='' 
    # Run the selection pipeline for a single run job #
    selection_pipeline_executable=config['selection_pipeline']['selection_pipeline_executable']
    for vcf, population_name in zip(output_vcfs, populations):
        directory=population_name
        # Create directory for each sub population to run in
        if not os.path.exists(directory):
            os.mkdir(directory)
        
        cmd=[]
        cmd.append(selection_pipeline_executable) 
        cmd.extend(['-c',options.chromosome,'-i',os.path.abspath(vcf),'-o',population_name,'--population',population_name,'--config-file',os.path.abspath(options.config_file)])
        cmd.append(extra_args)  
        os.chdir(directory)
        run_subprocess(cmd,'selection_pipeline')
        #running_log.close()
        os.chdir(orig_dir)
def fst_vcf(input_vcf,config,options,populations):
    vcf_tools =config['vcftools']['vcf_tools_executable']
    directory = 'fst'
    if not os.path.exists(directory):
        os.mkdir(directory)
    pops = list(populations.keys())
    orig_dir = os.getcwd()
    os.chdir(directory)
    for i in range(0,len(pops)-1):
        p = pops[i]
        cmd=[]
        cmd.append(vcf_tools)
        first_pop_name = open('first_pop.tmp','w')
        first_pop_name.write('\n'.join(populations[p]))
        first_pop_name.close()
        cmd.extend(['--fst-window-size',options.fst_window_size,'--fst-window-step',options.fst_window_step,'--weir-fst-pop','first_pop.tmp','--vcf',input_vcf])
        for j in range(i+1,len(pops)):
            s = pops[j]
            tmp_cmd = []
            tmp_cmd.extend(cmd)
            tmp_cmd.extend(['--weir-fst-pop','second_pop.tmp']) 
            second_pop_name = open('second_pop.tmp','w')
            second_pop_name.write('\n'.join(populations[s]))
            second_pop_name.close()
            run_subprocess(tmp_cmd,'fst_calculation')
            os.rename('out.windowed.weir.fst',options.chromosome + p + s + '.fst')
    os.remove('second_pop.tmp')
    os.remove('first_pop.tmp')        
 
    os.chdir(orig_dir)
def main():
    parser=OptionParser()
    parser.add_option('-p','--population',action='append',dest="populations",help='population_files')
    parser.add_option('-a','--arguments-selection-pipelines',dest="extra_args",help='Arguments to the selection pipeline script')
    parser.add_option('-l','--log-file',dest="log_file",help="Log file")
    parser.add_option('-i','--vcf-input-file',dest="vcf_input",help="VCF Input File")
    parser.add_option('-c','--chromosome',dest="chromosome",help="Chromosome label doesn't actually have to correspond to the real chromosome but is required to determine what output files to make")
    parser.add_option('--config-file',dest='config_file',help='Configuration File')
    parser.add_option('--fst-window-size',dest="fst_window_size",help="FST window size")
    parser.add_option('--fst-window-step',dest="fst_window_step",help="FST window step size")
    (options,args) = parser.parse_args()
    assert options.vcf_input is not None, "No VCF file has been specified as input"
    assert options.chromosome is not None, "No chromosome has been specified to the script"
    config = parse_config(options)
    if ( options.config_file == None):
       options.config_file = config['system']['default_config_file'] 
    if not (check_executables_and_scripts_exist(options,config)):
        sys.exit(CANNOT_FIND_EXECUTABLE)
    if options.fst_window_step is None:
        options.fst_window_step = str(1000)
    else:
        options.fst_window_step = str(options.fst_window_step)
    if options.log_file is None:
        options.log_file = 'multi_population.log'   
    if options.fst_window_size is None:
        options.fst_window_size = str(1000)
    else:
        options.fst_window_size = str(options.fst_window_size) 
    logging.basicConfig(format='%(asctime)s %(message)s',filename=options.log_file)
    set_environment(config['environment'])
    options.vcf_input = os.path.abspath(options.vcf_input)
    populations=get_populations(options.populations)
    populations=OrderedDict(sorted(populations.items(), key=lambda t: t[0]))
    output_fst =  fst_vcf(options.vcf_input,config,options,populations)
    output_vcfs = subset_vcf(options.vcf_input,config,populations)
    run_selection_pipeline(output_vcfs,options,populations,config)
    rsb(config,options,populations)
if __name__=="__main__":main()
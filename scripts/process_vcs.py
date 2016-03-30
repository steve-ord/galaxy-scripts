#!/usr/bin/env python
import subprocess
import os
import sys
import glob
import time
import datetime
import distutils.spawn
from astropy.io import fits as pyfits
from mwapy import ephem_utils

def getmeta(service='obs', params=None):
    """
    Function to call a JSON web service and return a dictionary:
    Given a JSON web service ('obs', find, or 'con') and a set of parameters as
    a Python dictionary, return a Python dictionary containing the result.
    Taken verbatim from http://mwa-lfd.haystack.mit.edu/twiki/bin/view/Main/MetaDataWeb
    """
    import urllib
    import urllib2
    import json

    # Append the service name to this base URL, eg 'con', 'obs', etc.
    BASEURL = 'http://mwa-metadata01.pawsey.org.au/metadata/'


    if params:
        data = urllib.urlencode(params)  # Turn the dictionary into a string with encoded 'name=value' pairs
    else:
        data = ''

    if service.strip().lower() in ['obs', 'find', 'con']:
        service = service.strip().lower()
    else:
        print "invalid service name: %s" % service
        return

    try:
        result = json.load(urllib2.urlopen(BASEURL + service + '?' + data))
    except urllib2.HTTPError as error:
        print "HTTP error from server: code=%d, response:\n %s" % (error.code, error.read())
        return
    except urllib2.URLError as error:
        print "URL or network error: %s" % error.reason
        return

    return result

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def mdir(path,description):
    try:
        os.mkdir(path)
        os.chmod(path,0761)
    except:
        if (os.path.exists(path)):
            print "{0} Directory Already Exists\n".format(description)
        else:
            sys.exit()

def ensure_metafits(metafits_file):
        if (os.path.isfile(metafits_file) == False):
            metafile_line = "wget  http://mwa-metadata01.pawsey.org.au/metadata/fits?obs_id=%d -O %s\n" % (opts.obs,metafits_file)
            subprocess.call(metafile_line,shell=True)


def obs_max_min(obs_id):
    """
    Small function to query the database and returns the times of the first and last file
    :param obs_id:
    :return:
    """
    from file_maxmin import getmeta

    obsinfo = getmeta(service='obs', params={'obs_id':str(obs_id)})
    times=[file[11:21] for file in obsinfo['files'] if is_number(file[11:21])] #Make a list of gps times excluding non-numbers from list
    obs_start = int(min(times))
    obs_end = int(max(times))
    return obs_start, obs_end

def sfreq(freqs):

    if len(freqs) != 24:
        print "There are not 24 coarse chans defined for this obs. Got: %s" % freqs
        return

 #   freqs.sort()   # It should already be sorted, but just in case...[SET] Commenting this out because sort() is ironically putting 2-digit channels out of order
    lowchans = [f for f in freqs if int(f) <= int(128)]
    print "lowchans", lowchans
    highchans = [f for f in freqs if int(f) > int(128)]
    print "highchans", highchans
    highchans.reverse()
    freqs = lowchans + highchans
    print "freqs", freqs
    return freqs


def get_frequencies(metafits):
	# TODO: for robustness, this should force the entries to be 3-digit numbers
    hdulist = pyfits.open(metafits)
    freq_array = hdulist[0].header['CHANNELS']
    return sfreq(freq_array.split(','))


def options (options): # TODO reformat this to print properly

    print "\noptions:\n"
    print "--mode {0}".format(options.mode)
    print "-B [1/0]\t Submit download jobs to the copyq - at the moment this mode will only download and will perform <NO> subsequent processing [%d] \n" % (opts['batch_download'])
    print "-b:\t GPS/UNIX time of the beginning [%d]]\n" % (opts['begin'])
    print "-c:\t Coarse channel count (how many to process) [%d]\n" % (opts['ncoarse_chan'])
    print "-d:\t Number of parallel downloads to envoke if using '-g' [%d]\n" % (opts['parallel_dl'])
    print "-e:\t GPS/UNIX time of the end [%d]\n" % (opts['end'])
 #   print "-g:\t Get the data? (True/False) add this to get fresh data from the archive [%s]\n" % (opts['get_data'])
    print "-i:\t Increment in seconds (how much we process at once) [%d]\n" % (opts['inc'])
    print "-j:\t [corrdir] Use Jones matrices from the RTS [%s,%s]\n" % (opts['useJones'],opts['corrdir'])
    print "-m:\t Beam forming mode (0 == NO BEAMFORMING 1==PSRFITS, 2==VDIF) [%d]\n" % (opts['mode'])
    print "-n:\t Number of fine channels per coarse channel [%d]\n" % (opts['nchan'])
    print "-o:\t obsid [%s]\n" % opts['obsid']
    print "-p:\t beam pointing [%s]\n" % opts['pointing']
    print "-s:\t single step (only process one increment and this is it (-1 == do them all) [%d]\n" % opts['single_step']
#    print "-r:\t [corrdir] Run the offline correlator - this will submit a job to process the .dat files into visibility sets into the specified directory. These are needed if you want an RTS calibration solution [%s]\n" % opts['corrdir']
    print "-G:\t Submit the beamformer/correlator job [Do it = %s]\n" % opts['Go']
#   print "-R:\t New VCS mode - requires the recombine operation [runRECOMBINE = %s]\n" % opts['runRECOMBINE']
    print "-w:\t Working root directory [%s]\n" % opts['root']
#    print "-z:\t Add to switch off PFB formation/testing [runPFB = %s]\n" % opts['runPFB']


def vcs_download(obsid, start_time, stop_time, increment, head, format, working_dir, parallel):
    print "Downloading files from archive"
    voltdownload = distutils.spawn.find_executable("voltdownload.py")
#    voltdownload = "/group/mwaops/stremblay/MWA_CoreUtils/voltage/scripts/voltdownload.py"
#   voltdownload = "python /home/fkirsten/software/galaxy-scripts/scripts/voltdownload.py"
    raw_dir = "{0}/raw".format(working_dir)
    mdir(raw_dir, "Raw")

    for time_to_get in range(start_time,stop_time,increment):
        get_data = "{0} --obs={1} --type={2} --from={3} --duration={4} --parallel={5} --dir={6}".format(voltdownload,obsid, format, time_to_get,(increment-1),parallel, raw_dir)
        if head:
            log_name="{0}/voltdownload_{1}.log".format(working_dir,time_to_get)
            with open(log_name, 'w') as log:
                subprocess.call(get_data, shell=True, stdout=log, stderr=log)
        else:
            voltdownload_batch = "{0}/batch/volt_{1}.batch".format(working_dir,time_to_get)
            check_batch = "{0}/batch/check_volt_{1}.batch".format(working_dir,time_to_get)
            volt_secs_to_run = datetime.timedelta(seconds=300*increment)
            check_secs_to_run = '15:00'
            volt_submit_line = "sbatch --time={0} --workdir={1} -M zeus --partition=copyq {2}\n".format(volt_secs_to_run,raw_dir,voltdownload_batch)
            check_submit_line = "sbatch --time={0} --workdir={1} -M zeus --partition=copyq -d afterany:${{SLURM_JOB_ID}} {2}\n".format(check_secs_to_run, raw_dir, check_batch)
            checks = distutils.spawn.find_executable("checks.py")
            with open(check_batch,'w') as batch_file:
                batch_line = "#!/bin/bash -l\n#SBATCH --export=NONE\n#SBATCH --output={0}/batch/check_volt_{1}.out.0\n".format(working_dir,time_to_get)
                batch_file.write(batch_line)
                batch_file.write('newcount=0\n')
                batch_file.write('let oldcount=$newcount-1\n')
                # increase the counter in voltdownload_batch by one each time
                batch_line = "sed -i -e \"s/oldcount=${{oldcount}}/oldcount=${{newcount}}/\" {0}\n".format(voltdownload_batch)
                batch_file.write(batch_line)
                batch_file.write('oldcount=$newcount; let newcount=$newcount+1\n')
                # change the name of the batch-output file according to the counter each time
                batch_line = "sed -i -e \"s/.out.${{oldcount}}/.out.${{newcount}}/\" {0}\n".format(voltdownload_batch)
                batch_file.write(batch_line)
                batch_line = "{0} -m download -o {1} -w {2} -b {3} -i {4}\n".format(checks, obsid, raw_dir, time_to_get, increment)
                batch_file.write(batch_line)
                #in case something went wrong resubmit the voltdownload script
                batch_line = "if [ $? -eq 1 ];then \n{0}\nfi\n".format(volt_submit_line)
                batch_file.write(batch_line)
                
            with open(voltdownload_batch,'w') as batch_file:
                batch_line = "#!/bin/bash -l\n#SBATCH --export=NONE\n#SBATCH --output={0}/batch/volt_{1}.out.1\n".format(working_dir,time_to_get)
                batch_file.write(batch_line)
                batch_file.write('oldcount=0\n')
                batch_file.write('let newcount=$oldcount+1\n')
                batch_file.write('if [ ${newcount} -gt 10 ]; then\n')
                batch_file.write('echo \"Tried ten times, this is silly. Aborting here.\";exit\n')
                batch_file.write('fi\n')
                # increase the counter in check_batch by one each time
                batch_line = "sed -i -e \"s/newcount=${{oldcount}}/newcount=${{newcount}}/\" {0}\n".format(check_batch)
                batch_file.write(batch_line)
                # change the name of the batch-output file according to the counter each time
                batch_line = "sed -i -e \"s/.out.${{oldcount}}/.out.${{newcount}}/\" {0}\n".format(check_batch)
                batch_file.write(batch_line)
                # submit check script before we start the download in case it is timed out
                batch_file.write(check_submit_line)
                batch_line = "%s\n" % (get_data)
                batch_file.write(batch_line)
                
            submit_cmd = subprocess.Popen(volt_submit_line,shell=True,stdout=subprocess.PIPE)
            continue


        try:
            os.chdir(working_dir)
        except:
            print "cannot open working dir:{0}".format(working_dir)
            sys.exit()
    

def vcs_recombine(obsid, start_time, stop_time, increment, working_dir):
    print "Running recombine on files"
    jobs_per_node = 8
    recombine = distutils.spawn.find_executable("recombine.py")
    #recombine = "/group/mwaops/stremblay/galaxy-scripts/scripts/recombine.py"
    checks = distutils.spawn.find_executable("checks.py")
    recombine_binary = "/group/mwaops/PULSAR/bin/recombine" # Hard coding this temporarily to ensure correct version of code is envoked
    for time_to_get in range(start_time,stop_time,increment):

        recombine_batch = "{0}/batch/recombine_{1}.batch".format(working_dir,time_to_get)
        check_batch = "{0}/batch/check_recombine_{1}.batch".format(working_dir,time_to_get)
        recombine_submit_line = "sbatch --partition=gpuq --workdir={0} {1}\n".format(working_dir,recombine_batch)
        check_submit_line = "sbatch --time=15:00 --workdir={0} --partition=gpuq -d afterany:${{SLURM_JOB_ID}} {1}\n".format(working_dir, check_batch)
        with open(check_batch,'w') as batch_file:
            batch_line = "#!/bin/bash -l\n#SBATCH --export=NONE\n#SBATCH --output={0}/batch/check_recombine_{1}.out.0\n".format(working_dir,time_to_get)
            batch_file.write(batch_line)
            batch_file.write('newcount=0\n')
            batch_file.write('let oldcount=$newcount-1\n')
            # increase the counter in recombine_batch by one each time
            batch_line = "sed -i -e \"s/oldcount=${{oldcount}}/oldcount=${{newcount}}/\" {0}\n".format(recombine_batch)
            batch_file.write(batch_line)
            batch_file.write('oldcount=$newcount; let newcount=$newcount+1\n')
            # change the name of the batch-output file according to the counter each time
            batch_line = "sed -i -e \"s/.out.${{oldcount}}/.out.${{newcount}}/\" {0}\n".format(recombine_batch)
            batch_file.write(batch_line)
            batch_line = "{0} -m recombine -o {1} -w {2}/combined/ -b {3} -i {4}\n".format(checks, obsid, working_dir, time_to_get, increment)
            batch_file.write(batch_line)
            #in case something went wrong resubmit the voltdownload script
            batch_line = "if [ $? -eq 1 ];then \n{0}\nfi\n".format(recombine_submit_line)
            batch_file.write(batch_line)
        with open(recombine_batch,'w') as batch_file:

            nodes = (increment+(-increment%jobs_per_node))//jobs_per_node + 1 # Integer division with ceiling result plus 1 for master node

            batch_line = "#!/bin/bash -l\n#SBATCH --time=06:00:00\n#SBATCH \n#SBATCH --output={0}/batch/recombine_{1}.out.1\n#SBATCH --export=NONE\n#SBATCH --nodes={2}\n".format(working_dir, time_to_get, nodes)
            batch_file.write(batch_line)
            batch_line = "module switch PrgEnv-cray PrgEnv-gnu\n"
            batch_file.write(batch_line)
            batch_line = "module load mpi4py\n"
            batch_file.write(batch_line)
            batch_line = "module load cfitsio\n"
            batch_file.write(batch_line)
            batch_file.write('oldcount=0\n')
            batch_file.write('let newcount=$oldcount+1\n')
            batch_file.write('if [ ${newcount} -gt 10 ]; then\n')
            batch_file.write('echo \"Tried ten times, this is silly. Aborting here.\";exit\n')
            batch_file.write('fi\n')
            # increase the counter in check_batch by one each time
            batch_line = "sed -i -e \"s/newcount=${{oldcount}}/newcount=${{newcount}}/\" {0}\n".format(check_batch)
            batch_file.write(batch_line)
            # change the name of the batch-output file according to the counter each time
            batch_line = "sed -i -e \"s/.out.${{oldcount}}/.out.${{newcount}}/\" {0}\n".format(check_batch)
            batch_file.write(batch_line)
            # submit check script before we start the download in case it is timed out
            batch_file.write(check_submit_line)

            if (stop_time - time_to_get) < increment:       # Trying to stop jobs from running over if they aren't perfectly divisible by increment
                increment = stop_time - time_to_get + 1

            if (jobs_per_node > increment):
                jobs_per_node = increment

            recombine_line = "aprun -n {0} -N {1} python {2} -o {3} -s {4} -w {5} -e{6}\n".format(increment,jobs_per_node,recombine,obsid,time_to_get,working_dir,recombine_binary)
            batch_file.write(recombine_line)


        submit_cmd = subprocess.Popen(recombine_submit_line,shell=True,stdout=subprocess.PIPE)
        jobid=""
        for line in submit_cmd.stdout:

            if "Submitted" in line:
                (word1,word2,word3,jobid) = line.split()
#                if (is_number(jobid)):
#                    submitted_jobs.append(jobid)
#                    submitted_times.append(time_to_get)



def vcs_correlate(obsid,start,stop,increment,working_dir):
    print "Correlating files"
    import os
    import astropy
    from astropy.time import Time
    import datetime
    import calendar

    corr_dir = "{0}/vis".format(working_dir)
    mdir(corr_dir, "Correlator Product")

    chan_list = get_frequencies(metafits_file)
    
    print "Input chan list is" , chan_list

    for time_to_get in range(start,stop,increment):
        inc_start = time_to_get
        inc_stop = time_to_get+increment
        for index,channel in enumerate(chan_list):
            gpubox_label = (index+1)
            f=[]
            for time_to_corr in range(inc_start,inc_stop,1):
                file_to_process = "{0}/combined/{1}_{2}_ch{3:0>2}.dat".format(working_dir,obsid,time_to_corr,channel)
                #check the file exists
                if (os.path.isfile(file_to_process) == True):
                    f.append(file_to_process)

            #now have a full list of files
            #for this increment 
            #and this channel
            if (len(f) > 0):
                corr_batch = "{0}/batch/correlator_{1}_gpubox{2:0>2}.batch".format(working_dir,inc_start,gpubox_label)

                with open(corr_batch, 'w') as batch_file:
                    batch_file.write("#!/bin/bash -l\n#SBATCH --nodes=1\n#SBATCH --export=NONE\n#SBATCH --output={0}.out\n".format(corr_batch))
                    batch_file.write('source /group/mwaops/PULSAR/psrBash.profile\n')
                    batch_file.write('module swap craype-ivybridge craype-sandybridge\n')
                to_corr = 0
                for file in f:
                    corr_line = ""
                    (current_time,ext) = os.path.splitext(os.path.basename(file))
                    (obsid,gpstime,chan) = current_time.split('_')
                    t = Time(int(gpstime), format='gps', scale='utc')
                    time_str =  t.datetime.strftime('%Y-%m-%d %H:%M:%S')

                    current_time = time.strptime(time_str, "%Y-%m-%d  %H:%M:%S")
                    unix_time = calendar.timegm(current_time)

                    corr_line = " aprun -n 1 -N 1 {0} -o {1}/{2} -s {3} -r 1 -i 100 -f 128 -n 4 -c {4:0>2} -d {5}\n".format("mwac_offline",corr_dir,obsid,unix_time,gpubox_label,file)
                    
                    with open(corr_batch, 'a') as batch_file:
                        batch_file.write(corr_line)
                        to_corr = to_corr+1

                secs_to_run = datetime.timedelta(seconds=10*to_corr)
                batch_submit_line = "sbatch --workdir={0} --time={1} --partition=gpuq {2}\n".format(corr_dir,secs_to_run,corr_batch)
                submit_cmd = subprocess.Popen(batch_submit_line,shell=True,stdout=subprocess.PIPE)
                jobid=""
                for line in submit_cmd.stdout:
                    if "Submitted" in line:
                        (word1,word2,word3,jobid) = line.split()





def coherent_beam(obs_id, start,stop,working_dir, metafile, nfine_chan, pointing, rts_flag_file=None):
    # Need to run get_delays and then the beamformer on each desired coarse channel
    DI_dir = working_dir+"/DIJ"
    RA = pointing[0]
    Dec = pointing[1]

    print "Running get_delays"
    P_dir = working_dir+"/pointings"
    mdir(P_dir, "Pointings")
    pointing_dir = "{0}/{1}_{2}".format(P_dir, RA, Dec)
    mdir(pointing_dir, "Pointing {0} {1}".format(RA, Dec))

    startjobs = True
    chan_list = get_frequencies(metafits_file)
    chan_index = 0
    get_delays_batch = "{0}/batch/gd_{1}_{2}.batch".format(working_dir,start, stop)
    bf_adjust_flags = distutils.spawn.find_executable("bf_adjust_flags.py")
    with open(get_delays_batch,'w') as batch_file:
        batch_line = "#!/bin/bash -l\n#SBATCH --export=NONE\n#SBATCH --output={0}/batch/gd_{1}_{2}.out\n".format(working_dir,start,stop)
        batch_file.write(batch_line)
        batch_file.write('source /group/mwaops/PULSAR/psrBash.profile\n')
        batch_file.write('module swap craype-ivybridge craype-sandybridge\n')
        for gpubox in ["{0:0>2}".format(i) for i in range(1,25)]:
            #DI_file = "{0}/{1}".format(DI_dir, ?) # Need to finish file path
            pointing_chan_dir = "{0}/{1}".format(pointing_dir,gpubox)
            mdir(pointing_chan_dir, "Pointing {0} {1} gpubox {2}".format(RA, Dec, gpubox))

            DI_file = "{0}/DI_JonesMatrices_node0{1}.dat".format(DI_dir, gpubox)
            channel_file = "{0}/channel".format(pointing_chan_dir)
            with open(channel_file,"w") as ch_file:
                ch_line = "{0}".format(chan_list[chan_index]);
                ch_file.write(ch_line)

            #ASSUMES 10kHz channels <beware>

            basefreq = int(chan_list[chan_index]) * 1.28e6 - 5e3 - 640e3  + 5e3
        
            print "Looking for ", DI_file
            if (os.path.isfile(DI_file)):
                ch_dir_line = "cd {0}\n".format(pointing_chan_dir)
                batch_file.write(ch_dir_line)
                delays_line = "get_delays -a {0} -b {1} -j {2} -m {3} -c -i -p -z {4} -o {5} -f {6} -n {7} -w 10000 -r {8} -d {9}\n".format(pointing_chan_dir,stop-start,DI_file,metafile,utctime,obs_id,basefreq,nfine_chan,RA,Dec) 
                batch_file.write(delays_line)
                if rts_flag_file:
                    flags_file = "{0}/flags.txt".format(pointing_chan_dir)
                    flag_line="{0} {1} {2}\n".format(bf_adjust_flags, rts_flag_file, flags_file)
                    batch_file.write(flag_line)
            else:
                print "WARNING: No Calibration Found for Channel {0}!".format(gpubox)
                startjobs = False

            chan_index = chan_index+1
    submit_line = "sbatch --time={0} --workdir={1} --partition=gpuq {2}\n".format("00:45:00", pointing_dir, get_delays_batch)
    print submit_line;
    if startjobs:
        output = subprocess.Popen(submit_line, stdout=subprocess.PIPE, shell=True).communicate()[0]
        # output is something like this: Submitted batch job 245521 on cluster zeus
        # as the beamformer can only run once delays are computed need to put in dependency on get_delay jobs.
        dependsOn = output.split(" ")[3].strip()
        #submit_cmd = subprocess.Popen(submit_line,shell=True,stdout=subprocess.PIPE)
        print "Forming coherent beam. \n"
        print "starts once Job {0} is done.\n".format(dependsOn)
    else:
        print "Not submitted. \n"
 
 
    # Run make_beam
    seconds_to_run = 60*(stop-start)
    if seconds_to_run > 86399.:
        secs_to_run = datetime.timedelta(seconds=86399)
    else:
        secs_to_run = datetime.timedelta(seconds=60*(stop-start))

    make_beam_batch = "{0}/batch/mb_{1}_{2}.batch".format(working_dir,RA,Dec)
    make_beam_batch_out = "mb_{1}_{2}.out".format(working_dir,RA,Dec)
    with open(make_beam_batch, 'w') as batch_file:
        batch_file.write("#!/bin/bash -l\n")
        nodes_line = "#SBATCH --nodes=24\n#SBATCH --export=NONE\n" 
        batch_file.write(nodes_line)
        output_line = "#SBATCH --output={0}/batch/{1}\n".format(working_dir,make_beam_batch_out)
        batch_file.write(output_line)
        time_line = "#SBATCH --time=%s\n" % (str(secs_to_run))
        batch_file.write(time_line)
        batch_file.write('source /group/mwaops/PULSAR/psrBash.profile\n')
        batch_file.write('module swap craype-ivybridge craype-sandybridge\n')
        # the beamformer runs on all files in /combined with a specific ending
        # thus we rename all relevant ones to .bf and rename back later.
        rename_files_line = "cd {0}/combined;for sec in `seq {1} {2}`;do for chan in {3}_$sec*ch*.dat; do mv $chan $chan.bf;done;done;cd {4}\n".format(working_dir, start, stop, opts.obs,pointing_dir)
        batch_file.write(rename_files_line)
        aprun_line = "aprun -n 24 -N 1 make_beam -e dat.bf -a 128 -n 128 -t 1 %s -c phases.txt -w flags.txt -d %s/combined -D %s/ %s psrfits_header.txt\n" % (jones,working_dir,pointing_dir,bf_mode_str)
        batch_file.write(aprun_line)
        rename_files_line = "cd {0}/combined;for i in *.bf;do mv $i `basename $i .bf`;done\n".format(working_dir)
        batch_file.write(rename_files_line)

    submit_line = "sbatch --workdir={0} --time={1} --partition=gpuq -d afterok:{2} {3}\n".format(pointing_dir,secs_to_run,dependsOn,make_beam_batch)
    print submit_line
    if startjobs:
        output = subprocess.Popen(submit_line, stdout=subprocess.PIPE, shell=True).communicate()[0]
        jobID = output.split(" ")[3].strip()
        #submit_cmd = subprocess.Popen(submit_line,shell=True,stdout=subprocess.PIPE)
        print "Submitted as job {0}".format(jobID)
    else:
      print "Not submitted. \n"

if __name__ == '__main__':

    modes=['download','recombine','correlate','beamform']
    jobs_per_node = 8
    chan_list_full=["ch01","ch02","ch03","ch04","ch05","ch06","ch07","ch08","ch09","ch10","ch11","ch12","ch13","ch14","ch15","ch16","ch17","ch18","ch19","ch20","ch21","ch22","ch23","ch24"]
    chan_list = []
    utctime = "Never"
    bf_mode_str = " -f "
    jones = "-j jones.txt"

    from optparse import OptionParser, OptionGroup

 #   parser=OptionParser(description="process_vcs.py is a script of scripts that downloads prepares and submits jobs to Galaxy. It can be run with just a pointing (-p \"xx:xx:xx xx:xx:xx.x\") and an obsid (\"-o <obsid>\") and it will process all the data in the obs. It will call prepare.py which will attempt to build the phase and calibration information - which will only exist if a calibration obs has already been run. So it will only move past the data prepa stage if the \"-r\" (for run) is used\n"

    parser=OptionParser(description="process_vcs.py is a script for processing the MWA VCS data on Galaxy in steps. It can download data from the archive, call on recombine to form course channels, run the offline correlator, make tile re-ordered and bit promoted PFB files or for a coherent beam for a given pointing.")
    group_download = OptionGroup(parser, 'Download Options')
    group_download.add_option("--head", action="store_true", default=False, help="Submit download jobs to the headnode instead of the copyqueue [default=%default]")
    group_download.add_option("--format", type="choice", choices=['11','12'], default='11', help="Voltage data type (Raw = 11, Recombined Raw = 12) [default=%default]")
    group_download.add_option("-d", "--parallel_dl", type="int", default=3, help="Number of parallel downloads to envoke [default=%default]")

    group_recombine = OptionGroup(parser, 'Recombine Options')

    group_correlate = OptionGroup(parser, 'Correlator Options')
    group_correlate.add_option("--ft_res", metavar="FREQ RES,TIME RES", type="int", nargs=2, default=(40,1), help="Frequency (kHz) and Time (s) resolution to run correlator at. [default=%default]")

    group_pfb = OptionGroup(parser, 'PFB Creation Options')

    group_beamform = OptionGroup(parser, 'Beamforming Options')
    group_beamform.add_option("-p", "--pointing", nargs=2, help="R.A. and Dec. of pointing")
    group_beamform.add_option("--bf_mode", type="choice", choices=['0','1','2'], help="Beam forming mode (0 == NO BEAMFORMING 1==PSRFITS, 2==VDIF)")
    group_beamform.add_option("-j", "--useJones", action="store_true", default=False, help="Use Jones matrices from the RTS [default=%default]")
    group_beamform.add_option("--flagged_tiles", type="string", default=None, help="absolute path to file containing the flagged tiles as used in the RTS, will be used to adjust flags.txt as output by get_delays. [default=%default]")

    parser.add_option("-m", "--mode", type="choice", choices=['download','recombine','correlate','beamform'], help="Mode you want to run. {0}".format(modes))
    parser.add_option("-o", "--obs", metavar="OBS ID", type="int", help="Observation ID you want to process [no default]")
    parser.add_option("-b", "--begin", type="int", help="First GPS time to process [no default]")
    parser.add_option("-e", "--end", type="int", help="Last GPS time to process [no default]")
    parser.add_option("-a", "--all", action="store_true", default=False, help="Perform on entire observation span. Use instead of -b & -e. [default=%default]")
    parser.add_option("-i", "--increment", type="int", default=64, help="Increment in seconds (how much we process at once) [default=%default]")
    parser.add_option("-s", action="store_true", default=False, help="Single step (only process one increment and this is it (False == do them all) [default=%default]")
    parser.add_option("-w", "--work_dir", metavar="DIR", default="/scratch2/mwaops/vcs/", help="Base directory you want to run from. This will create a folder for the Obs. ID if it doesn't exist [default=%default]")
    parser.add_option("-c", "--ncoarse_chan", type="int", default=24, help="Coarse channel count (how many to process) [default=%default]")
    parser.add_option("-n", "--nfine_chan", type="int", default=128, help="Number of fine channels per coarse channel [default=%default]")
    parser.add_option_group(group_download)
#    parser.add_option_group(group_recombine)
    parser.add_option_group(group_correlate)
#   parser.add_option_group(group_pfb)
    parser.add_option_group(group_beamform)

    (opts, args) = parser.parse_args()
    
    if opts.all and (opts.begin or opts.end):
        print "Please specify EITHER (-b,-e) OR -a"
        quit()
    elif opts.all:
        opts.begin, opts.end = obs_max_min(opts.obs)
    if not opts.mode:
      print "Mode required {0}. Please specify with -m or --mode.".format(modes)
      quit()
    if not opts.obs:
        print "Observation ID required, please put in with -o or --obs"
        quit()
    if opts.begin > opts.end:
        print "Starting time is after end time"
        quit()
    if opts.mode == "beamform":
        if not opts.pointing:
            print "Pointing (-p) required in beamformer mode"
            quit()
        # get_delays requires the start time in UTC, get it from the start GPS time
        # as is done in timeconvert.py
        t=ephem_utils.MWATime(gpstime=float(opts.begin))
        utctime = t.strftime('%Y-%m-%dT%H:%M:%S %Z')[:-4]
        if (opts.bf_mode == 1):
            bf_mode_str = " -f "
        if  (opts.bf_mode == 2):
            bf_mode_str = " -v "


    mdir(opts.work_dir, "Working")
    obs_dir = "{0}/{1}".format(opts.work_dir,opts.obs)
    mdir(obs_dir, "Observation")
    batch_dir = "{0}/batch".format(obs_dir)
    mdir(batch_dir, "Batch")
    metafits_file = "{0}/{1}.metafits".format(obs_dir,opts.obs)

 #   options(opts)
    print "Processing Obs ID {0} from GPS times {1} till {2}".format(opts.obs, opts.begin, opts.end)

    if opts.mode == 'download':
        print opts.mode
        vcs_download(opts.obs, opts.begin, opts.end, opts.increment, opts.head, opts.format, obs_dir, opts.parallel_dl)
    elif opts.mode == 'recombine':
        print opts.mode
        ensure_metafits(metafits_file)
        combined_dir = "{0}/combined".format(obs_dir)
        mdir(combined_dir, "Combined")
        vcs_recombine(opts.obs, opts.begin, opts.end, opts.increment, obs_dir)
    elif opts.mode == 'correlate':
        print opts.mode 
        ensure_metafits(metafits_file)
        vcs_correlate(opts.obs, opts.begin, opts.end, opts.increment, obs_dir)
    elif opts.mode == 'beamform':
        print opts.mode
        ensure_metafits(metafits_file)
        coherent_beam(opts.obs, opts.begin, opts.end,obs_dir, metafits_file, opts.nfine_chan, opts.pointing, opts.flagged_tiles)
    else:
        print "Somehow your non-standard mode snuck through. Try again with one of {0}".format(modes)
        quit()



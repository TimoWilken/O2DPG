#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow 
# It aims to handle the different MC possible configurations 
# It just creates a workflow.json txt file, to execute the workflow one must execute right after
#   ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json 
#
# Execution examples:
#  - pp PYTHIA jets, 2 events, triggered on high pT decay photons on EMCal acceptance, eCMS 13 TeV
#     ./o2dpg_sim_workflow.py -e TGeant3 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC" -col pp -eCM 13000 \
#                             -proc "jets" -ptTrigMin 3.5 -acceptance 4 -ptHatBin 3 \
#                             -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma.ini"
#
#  - pp PYTHIA ccbar events embedded into heavy-ion environment, 2 PYTHIA events into 1 bkg event, beams energy 2.510
#     ./o2dpg_sim_workflow.py -e TGeant3 -nb 1 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC"  \
#                             -col pp -eA 2.510 -proc "ccbar"  --embedding
# 

import argparse
from os import environ
import json
import array as arr

parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

parser.add_argument('-ns',help='number of signal events / timeframe', default=20)
parser.add_argument('-gen',help='generator: pythia8, extgen', default='pythia8')
parser.add_argument('-proc',help='process type: dirgamma, jets, ccbar', default='')
parser.add_argument('-trigger',help='event selection: particle, external', default='')
parser.add_argument('-ini',help='generator init parameters file, for example: ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini', default='')
parser.add_argument('-confKey',help='generator or trigger configuration key values, for example: GeneratorPythia8.config=pythia8.cfg', default='')

parser.add_argument('-interactionRate',help='Interaction rate, used in digitization', default=-1)
parser.add_argument('-eCM',help='CMS energy', default=-1)
parser.add_argument('-eA',help='Beam A energy', default=6499.) #6369 PbPb, 2.510 pp 5 TeV, 4 pPb
parser.add_argument('-eB',help='Beam B energy', default=-1)
parser.add_argument('-col',help='collision sytem: pp, PbPb, pPb, Pbp, ...', default='pp')
parser.add_argument('-ptHatBin',help='pT hard bin number', default=-1)
parser.add_argument('-ptHatMin',help='pT hard minimum when no bin requested', default=0)
parser.add_argument('-ptHatMax',help='pT hard maximum when no bin requested', default=-1)
parser.add_argument('-weightPow',help='Flatten pT hard spectrum with power', default=-1)

parser.add_argument('-ptTrigMin',help='generated pT trigger minimum', default=0)
parser.add_argument('-ptTrigMax',help='generated pT trigger maximum', default=-1)
parser.add_argument('-acceptance',help='select particles within predefined acceptance in ${O2DPG_ROOT}/MC/run/common/detector_acceptance.C', default=0)

parser.add_argument('--embedding',action='store_true', help='With embedding into background')
parser.add_argument('-nb',help='number of background events / timeframe', default=20)
parser.add_argument('-genBkg',help='generator', default='pythia8hi')
parser.add_argument('-iniBkg',help='generator init parameters file', default='${O2DPG_ROOT}/MC/config/common/ini/basic.ini')

parser.add_argument('-e',help='simengine', default='TGeant4')
parser.add_argument('-tf',help='number of timeframes', default=2)
parser.add_argument('-j',help='number of workers (if applicable)', default=8)
parser.add_argument('-mod',help='Active modules', default='--skipModules ZDC')
parser.add_argument('-seed',help='random seed number', default=0)
parser.add_argument('-o',help='output workflow file', default='workflow.json')
parser.add_argument('--noIPC',help='disable shared memory in DPL')

# arguments for background event caching
parser.add_argument('--upload-bkg-to',help='where to upload background event files (alien path)')
parser.add_argument('--use-bkg-from',help='take background event from given alien path')
# power feature (for playing) --> does not appear in help message
#  help='Treat smaller sensors in a single digitization')
parser.add_argument('--combine-smaller-digi', action='store_true', help=argparse.SUPPRESS)

args = parser.parse_args()
print (args)

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')
O2_ROOT=environ.get('O2_ROOT')

if O2DPG_ROOT == None: 
   print('Error: This needs O2DPG loaded')
#   exit(1)

if O2_ROOT == None: 
   print('Error: This needs O2 loaded')
#   exit(1)

# ----------- START WORKFLOW CONSTRUCTION ----------------------------- 

NTIMEFRAMES=int(args.tf)
NWORKERS=args.j
MODULES=args.mod #"--skipModules ZDC"
SIMENGINE=args.e

# add here other possible types

workflow={}
workflow['stages'] = []

taskcounter=0
def createTask(name='', needs=[], tf=-1, cwd='./', lab=[], cpu=0, mem=0):
    global taskcounter
    taskcounter = taskcounter + 1
    return { 'name': name, 'cmd':'', 'needs': needs, 'resources': { 'cpu': cpu , 'mem': mem }, 'timeframe' : tf, 'labels' : lab, 'cwd' : cwd }

def getDPL_global_options(bigshm=False,nosmallrate=False):
   if args.noIPC!=None:
      return "-b --run --no-IPC " + ('--rate 1000','')[nosmallrate]
   if bigshm:
      return "-b --run --shm-segment-size ${SHMSIZE:-50000000000} --session " + str(taskcounter) + ' --driver-client-backend ws://' + (' --rate 1000','')[nosmallrate]
   else:
      return "-b --run --session " + str(taskcounter) + ' --driver-client-backend ws://' + (' --rate 1000','')[nosmallrate]

doembedding=True if args.embedding=='True' or args.embedding==True else False
usebkgcache=args.use_bkg_from!=None

if doembedding:
    if not usebkgcache:
        # ---- do background transport task -------
        NBKGEVENTS=args.nb
        GENBKG=args.genBkg
        INIBKG=args.iniBkg
        BKGtask=createTask(name='bkgsim', lab=["GEANT"], cpu='8')
        BKGtask['cmd']='o2-sim -e ' + SIMENGINE + ' -j ' + str(NWORKERS) + ' -n ' + str(NBKGEVENTS) + ' -g  ' + str(GENBKG) + ' ' + str(MODULES) + ' -o bkg --configFile ' + str(INIBKG)
        workflow['stages'].append(BKGtask)

        # check if we should upload background event
        if args.upload_bkg_to!=None:
            BKGuploadtask=createTask(name='bkgupload', needs=[BKGtask['name']], cpu='0')
            BKGuploadtask['cmd']='alien.py mkdir ' + args.upload_bkg_to + ';'
            BKGuploadtask['cmd']+='alien.py cp -f bkg* ' + args.upload_bkg_to + ';'
            workflow['stages'].append(BKGuploadtask)

    else:
        # here we are reusing existing background events from ALIEN

        # when using background caches, we have multiple smaller tasks
        # this split makes sense as they are needed at different stages
        # 1: --> download bkg_MCHeader.root + grp + geometry
        # 2: --> download bkg_Hit files (individually)
        # 3: --> download bkg_Kinematics
        # (A problem with individual copying might be higher error probability but
        #  we can introduce a "retry" feature in the copy process)

        # Step 1: header and link files
        BKG_HEADER_task=createTask(name='bkgdownloadheader', cpu='0', lab=['BKGCACHE'])
        BKG_HEADER_task['cmd']='alien.py cp ' + args.use_bkg_from + 'bkg_MCHeader.root .'
        BKG_HEADER_task['cmd']=BKG_HEADER_task['cmd'] + ';alien.py cp ' + args.use_bkg_from + 'bkg_geometry.root .'
        BKG_HEADER_task['cmd']=BKG_HEADER_task['cmd'] + ';alien.py cp ' + args.use_bkg_from + 'bkg_grp.root .'
        workflow['stages'].append(BKG_HEADER_task)

# a list of smaller sensors (used to construct digitization tasks in a parametrized way)
smallsensorlist = [ "ITS", "TOF", "FT0", "FV0", "FDD", "MCH", "MID", "MFT", "HMP", "EMC", "PHS", "CPV" ]

BKG_HITDOWNLOADER_TASKS={}
for det in [ 'TPC', 'TRD' ] + smallsensorlist:
   if usebkgcache:
      BKG_HITDOWNLOADER_TASKS[det] = createTask(str(det) + 'hitdownload', cpu='0', lab=['BKGCACHE'])
      BKG_HITDOWNLOADER_TASKS[det]['cmd'] = 'alien.py cp ' + args.use_bkg_from + 'bkg_Hits' + str(det) + '.root .'
      workflow['stages'].append(BKG_HITDOWNLOADER_TASKS[det])
   else:
      BKG_HITDOWNLOADER_TASKS[det] = None

if usebkgcache:
   BKG_KINEDOWNLOADER_TASK = createTask(name='bkgkinedownload', cpu='0', lab=['BKGCACHE'])
   BKG_KINEDOWNLOADER_TASK['cmd'] = 'alien.py cp ' + args.use_bkg_from + 'bkg_Kine.root .'
   workflow['stages'].append(BKG_KINEDOWNLOADER_TASK)

# loop over timeframes
for tf in range(1, NTIMEFRAMES + 1):
   timeframeworkdir='tf'+str(tf)

   # ----  transport task -------
   # function encapsulating the signal sim part
   # first argument is timeframe id
   RNDSEED=args.seed    # 0 means random seed !
   ECMS=float(args.eCM)
   EBEAMA=float(args.eA)
   EBEAMB=float(args.eB)
   NSIGEVENTS=args.ns
   GENERATOR=args.gen
   INIFILE=''
   if args.ini!= '':
      INIFILE=' --configFile ' + args.ini
   CONFKEY=''
   if args.confKey!= '':
      CONFKEY=' --configKeyValue ' + args.confKey
   PROCESS=args.proc
   TRIGGER=''
   if args.trigger != '':
      TRIGGER=' -t ' + args.trigger
   
   PTTRIGMIN=float(args.ptTrigMin)  
   PTTRIGMAX=float(args.ptTrigMax) 
   PARTICLE_ACCEPTANCE=int(args.acceptance)

   ## Pt Hat productions
   WEIGHTPOW=int(args.weightPow)

   # Recover PTHATMIN and PTHATMAX from pre-defined array depending bin number PTHATBIN
   # or just the ones passed
   PTHATBIN=int(args.ptHatBin)  
   PTHATMIN=int(args.ptHatMin)  
   PTHATMAX=int(args.ptHatMax) 
   # I would move next lines to a external script, not sure how to do it (GCB)
   if PTHATBIN > -1:
           # gamma-jet 
      if   PROCESS == 'dirgamma': 
           low_edge = arr.array('l', [5,  11, 21, 36, 57, 84])
           hig_edge = arr.array('l', [11, 21, 36, 57, 84, -1])
           PTHATMIN=low_edge[PTHATBIN]
           PTHATMAX=hig_edge[PTHATBIN]
           # jet-jet
      elif PROCESS == 'jets': 
          # Biased jet-jet
          # Define the pt hat bin arrays and set bin depending threshold
           if   PTTRIGMIN == 3.5:
                low_edge = arr.array('l', [5, 7,  9, 12, 16, 21])
                hig_edge = arr.array('l', [7, 9, 12, 16, 21, -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
           elif PTTRIGMIN == 7:
                low_edge = arr.array('l', [ 8, 10, 14, 19, 26, 35, 48, 66])
                hig_edge = arr.array('l', [10, 14, 19, 26, 35, 48, 66, -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
           #unbiased
           else:
                low_edge = arr.array('l', [ 0, 5, 7,  9, 12, 16, 21, 28, 36, 45, 57, 70, 85,  99, 115, 132, 150, 169, 190, 212, 235])
                hig_edge = arr.array('l', [ 5, 7, 9, 12, 16, 21, 28, 36, 45, 57, 70, 85, 99, 115, 132, 150, 169, 190, 212, 235,  -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
      else:
           low_edge = arr.array('l', [ 0, 5, 7,  9, 12, 16, 21, 28, 36, 45, 57, 70, 85,  99, 115, 132, 150, 169, 190, 212, 235])
           hig_edge = arr.array('l', [ 5, 7, 9, 12, 16, 21, 28, 36, 45, 57, 70, 85, 99, 115, 132, 150, 169, 190, 212, 235,  -1])
           PTHATMIN=low_edge[PTHATBIN]
           PTHATMAX=hig_edge[PTHATBIN]
           
   # translate here collision type to PDG
   COLTYPE=args.col

   if COLTYPE == 'pp':
      PDGA=2212 # proton
      PDGB=2212 # proton

   if COLTYPE == 'PbPb':
      PDGA=1000822080 # Pb
      PDGB=1000822080 # Pb
      if ECMS < 0:    # assign 5.02 TeV to Pb-Pb
         print('o2dpg_sim_workflow: Set CM Energy to PbPb case 5.02 TeV')
         ECMS=5020.0

   if COLTYPE == 'pPb':
      PDGA=2212       # proton
      PDGB=1000822080 # Pb

   if COLTYPE == 'Pbp':
      PDGA=1000822080 # Pb
      PDGB=2212       # proton

   # If not set previously, set beam energy B equal to A
   if EBEAMB < 0 and ECMS < 0:
      EBEAMB=EBEAMA
      print('o2dpg_sim_workflow: Set beam energy same in A and B beams')
      if COLTYPE=="pPb" or COLTYPE=="Pbp":
         print('o2dpg_sim_workflow: Careful! both beam energies are the same')

   if ECMS > 0:
      if COLTYPE=="pPb" or COLTYPE=="Pbp":
         print('o2dpg_sim_workflow: Careful! ECM set for pPb/Pbp collisions!')

   if ECMS < 0 and EBEAMA < 0 and EBEAMB < 0:
      print('o2dpg_sim_workflow: Error! CM or Beam Energy not set!!!')
      exit(1)

   # produce the signal configuration
   SGN_CONFIG_task=createTask(name='gensgnconf_'+str(tf), tf=tf, cwd=timeframeworkdir)
   if GENERATOR == 'pythia8':
      SGN_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
                --output=pythia8.cfg \
	              --seed='+str(RNDSEED)+' \
	              --idA='+str(PDGA)+' \
	              --idB='+str(PDGB)+' \
	              --eCM='+str(ECMS)+' \
	              --process='+str(PROCESS)+' \
	              --ptHatMin=' + str(PTHATMIN) + ' \
	              --ptHatMax=' + str(PTHATMAX)
      if WEIGHTPOW   > -1:
            SGN_CONFIG_task['cmd'] = SGN_CONFIG_task['cmd'] + ' --weightPow=' + str(WEIGHTPOW)
      workflow['stages'].append(SGN_CONFIG_task) 
   # elif GENERATOR == 'extgen': what do we do if generator is not pythia8?
       # NOTE: Generator setup might be handled in a different file or different files (one per
       # possible generator)

   # -----------------
   # transport signals
   # -----------------
   signalprefix='sgn_' + str(tf)
   signalneeds=[ SGN_CONFIG_task['name'] ]
   embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if doembedding else ""
   if doembedding:
       if not usebkgcache:
            signalneeds = signalneeds + [ BKGtask['name'] ]
       else:
            signalneeds = signalneeds + [ BKG_HEADER_task['name'] ]
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"], cpu='5.')
   SGNtask['cmd']='o2-sim -e ' + str(SIMENGINE) + ' ' + str(MODULES) + ' -n ' + str(NSIGEVENTS) +  ' -j ' \
                  + str(NWORKERS) + ' -g ' + str(GENERATOR) + ' ' + str(TRIGGER)+ ' ' + str(CONFKEY) \
                  + ' ' + str(INIFILE) + ' -o ' + signalprefix + ' ' + embeddinto
   workflow['stages'].append(SGNtask)

   # some tasks further below still want geometry + grp in fixed names, so we provide it here
   # Alternatively, since we have timeframe isolation, we could just work with standard o2sim_ files
   # We need to be careful here and distinguish between embedding and non-embedding cases
   # (otherwise it can confuse itstpcmatching, see O2-2026). This is because only one of the GRPs is updated during digitization.
   if doembedding:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[BKG_HEADER_task['name'] if usebkgcache else BKGtask['name'] ], tf=tf, cwd=timeframeworkdir)
      LinkGRPFileTask['cmd']='''
                             ln -nsf ../bkg_grp.root o2sim_grp.root;
                             ln -nsf ../bkg_geometry.root o2sim_geometry.root;
                             ln -nsf ../bkg_geometry.root bkg_geometry.root;
                             ln -nsf ../bkg_grp.root bkg_grp.root
                             '''
   else:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[SGNtask['name']], tf=tf, cwd=timeframeworkdir)
      LinkGRPFileTask['cmd']='ln -nsf ' + signalprefix + '_grp.root o2sim_grp.root ; ln -nsf ' + signalprefix + '_geometry.root o2sim_geometry.root'
   workflow['stages'].append(LinkGRPFileTask)

   # ------------------
   # digitization steps
   # ------------------
   CONTEXTFILE='collisioncontext.root'
 
   INTRATE=int(args.interactionRate)

   #it should be taken from CDB, meanwhile some default values
   if INTRATE < 0:
      if   COLTYPE=="PbPb":
         INTRATE=50000 #Hz
      elif COLTYPE=="pp":
         INTRATE=400000 #Hz
      else: #pPb?
         INTRATE=200000 #Hz ???

   simsoption=' --sims ' + ('bkg,'+signalprefix if doembedding else signalprefix)

   ContextTask=createTask(name='digicontext_'+str(tf), needs=[SGNtask['name'], LinkGRPFileTask['name']], tf=tf,
                          cwd=timeframeworkdir, lab=["DIGI"], cpu='1')
   ContextTask['cmd'] = 'o2-sim-digitizer-workflow --only-context --interactionRate ' + str(INTRATE) + ' ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption
   workflow['stages'].append(ContextTask)

   tpcdigineeds=[ContextTask['name'], LinkGRPFileTask['name']]
   if usebkgcache:
      tpcdigineeds += [ BKG_HITDOWNLOADER_TASKS['TPC']['name'] ]

   TPCDigitask=createTask(name='tpcdigi_'+str(tf), needs=tpcdigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='8', mem='9000')
   TPCDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTPC.root . ;')[doembedding]
   TPCDigitask['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TPC --interactionRate ' + str(INTRATE) + '  --tpc-lanes ' + str(NWORKERS) + ' --incontext ' + str(CONTEXTFILE) + ' --tpc-chunked-writer'
   workflow['stages'].append(TPCDigitask)

   trddigineeds = [ContextTask['name']]
   if usebkgcache:
      trddigineeds += [ BKG_HITDOWNLOADER_TASKS['TRD']['name'] ]
   TRDDigitask=createTask(name='trddigi_'+str(tf), needs=trddigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='8', mem='8000')
   TRDDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTRD.root . ;')[doembedding]
   TRDDigitask['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TRD --interactionRate ' + str(INTRATE) + '  --configKeyValues \"TRDSimParams.digithreads=' + str(NWORKERS) + '\" --incontext ' + str(CONTEXTFILE)
   workflow['stages'].append(TRDDigitask)

   # these are digitizers which are single threaded
   def createRestDigiTask(name, det='ALLSMALLER'):
      tneeds = needs=[ContextTask['name']]
      if det=='ALLSMALLER':
         if usebkgcache:
            for d in smallsensorlist:
               tneeds += [ BKG_HITDOWNLOADER_TASKS[d]['name'] ]
         t = createTask(name=name, needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='8')
         t['cmd'] = ('','ln -nfs ../bkg_Hits*.root . ;')[doembedding]
         t['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options(nosmallrate=True) + ' -n ' + str(args.ns) + simsoption + ' --skipDet TPC,TRD --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE)
         workflow['stages'].append(t)
         return t

      else:
         if usebkgcache:
            tneeds += [ BKG_HITDOWNLOADER_TASKS[det]['name'] ]
         t = createTask(name=name, needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
         t['cmd'] = ('','ln -nfs ../bkg_Hits' + str(det) + '.root . ;')[doembedding]
         t['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet ' + str(det) + ' --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE)
         workflow['stages'].append(t)
         return t

   det_to_digitask={}

   if args.combine_smaller_digi==True:
      det_to_digitask['ALLSMALLER']=createRestDigiTask("restdigi_"+str(tf))

   for det in smallsensorlist:
      name=str(det).lower() + "digi_" + str(tf)
      t = det_to_digitask['ALLSMALLER'] if args.combine_smaller_digi==True else createRestDigiTask(name, det)
      det_to_digitask[det]=t

   # -----------
   # reco
   # -----------

   # TODO: check value for MaxTimeBin; A large value had to be set tmp in order to avoid crashes based on "exceeding timeframe limit"
   # We treat TPC clusterization in multiple (sector) steps in order to stay within the memory limit
   TPCCLUStask1=createTask(name='tpcclusterpart1_'+str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='8', mem='16000')
   TPCCLUStask1['cmd'] = 'o2-tpc-chunkeddigit-merger --tpc-sectors 0-17 --rate 1 --tpc-lanes ' + str(NWORKERS) + ' --session ' + str(taskcounter)
   TPCCLUStask1['cmd'] += ' | o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True, nosmallrate=False) + ' --input-type digitizer --output-type clusters,send-clusters-per-sector --outfile tpc-native-clusters-part1.root --tpc-sectors 0-17 --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads='+str(NWORKERS)+'"'
   workflow['stages'].append(TPCCLUStask1)

   TPCCLUStask2=createTask(name='tpcclusterpart2_'+str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='8', mem='16000')
   TPCCLUStask2['cmd'] = 'o2-tpc-chunkeddigit-merger --tpc-sectors 18-35 --rate 1 --tpc-lanes ' + str(NWORKERS) + ' --session ' + str(taskcounter)
   TPCCLUStask2['cmd'] += ' | o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True, nosmallrate=False) + ' --input-type digitizer --output-type clusters,send-clusters-per-sector --outfile tpc-native-clusters-part2.root --tpc-sectors 18-35 --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads='+str(NWORKERS)+'"'
   workflow['stages'].append(TPCCLUStask2)

   # additional file merge step (TODO: generalize to arbitrary number of files)
   TPCCLUSMERGEtask=createTask(name='tpcclustermerge_'+str(tf), needs=[TPCCLUStask1['name'], TPCCLUStask2['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1')
   TPCCLUSMERGEtask['cmd']='o2-commonutils-treemergertool -i tpc-native-clusters-part*.root -o tpc-native-clusters.root -t tpcrec' #--asfriend preferable but does not work
   workflow['stages'].append(TPCCLUSMERGEtask)

   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=[TPCCLUSMERGEtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='3', mem='16000')
   TPCRECOtask['cmd'] = 'o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True, nosmallrate=False) + ' --input-type clusters --output-type tracks,send-clusters-per-sector --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads='+str(NWORKERS)+'"'
   workflow['stages'].append(TPCRECOtask)

   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[det_to_digitask["ITS"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   ITSRECOtask['cmd'] = 'o2-its-reco-workflow --trackerCA --tracking-mode async ' + getDPL_global_options()
   workflow['stages'].append(ITSRECOtask)

   FT0RECOtask=createTask(name='ft0reco_'+str(tf), needs=[det_to_digitask["FT0"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   FT0RECOtask['cmd'] = 'o2-ft0-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(FT0RECOtask)

   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', cpu='3')
   ITSTPCMATCHtask['cmd']= 'o2-tpcits-match-workflow ' + getDPL_global_options(bigshm=True, nosmallrate=False) + ' --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\"'
   workflow['stages'].append(ITSTPCMATCHtask)

   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDDigitask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   TRDTRACKINGtask['cmd'] = 'echo "would do TRD tracking"' # 'o2-trd-global-tracking'
   workflow['stages'].append(TRDTRACKINGtask)

   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], det_to_digitask["TOF"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   TOFRECOtask['cmd'] = 'o2-tof-reco-workflow ' + getDPL_global_options(nosmallrate=False)
   workflow['stages'].append(TOFRECOtask)

   TOFTPCMATCHERtask = createTask(name='toftpcmatch_'+str(tf), needs=[TOFRECOtask['name'], TPCRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   TOFTPCMATCHERtask['cmd'] = 'o2-tof-matcher-tpc ' + getDPL_global_options()
   workflow['stages'].append(TOFTPCMATCHERtask)

   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=[ITSTPCMATCHtask['name'], FT0RECOtask['name'], TOFTPCMATCHERtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='8', mem='4000')
   PVFINDERtask['cmd'] = 'o2-primary-vertexing-workflow ' + getDPL_global_options(nosmallrate=False)
   workflow['stages'].append(PVFINDERtask)
 
  # -----------
  # produce AOD
  # -----------
   aodneeds = [PVFINDERtask['name'], TOFRECOtask['name'], TRDTRACKINGtask['name']]
   if usebkgcache:
     aodneeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   AODtask = createTask(name='aod_'+str(tf), needs=aodneeds, tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='4000', cpu='1')
   AODtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   AODtask['cmd'] += 'o2-aod-producer-workflow --reco-mctracks-only 1 --aod-writer-keep dangling --aod-writer-resfile \"AO2D\" --aod-writer-resmode UPDATE --aod-timeframe-id ' + str(tf) + ' ' + getDPL_global_options(bigshm=True)
   workflow['stages'].append(AODtask)

def trimString(cmd):
  return ' '.join(cmd.split())

# insert taskwrapper stuff
for s in workflow['stages']:
  s['cmd']='. ${O2_ROOT}/share/scripts/jobutils.sh; taskwrapper ' + s['name']+'.log \'' + s['cmd'] + '\''

# remove whitespaces etc
for s in workflow['stages']:
  s['cmd']=trimString(s['cmd'])


# write workflow to json
workflowfile=args.o
with open(workflowfile, 'w') as outfile:
    json.dump(workflow, outfile, indent=2)

exit (0)

#!/usr/bin/env python

'''
Example python script using anlffr functions, meant to be called from the
command line.  This was originally created to analyze data from a Brainvision
EEG system that was already preprocessed in Matlab. There were three conditions
with two polarities each, stored in files of the form
'subjectname_S_trgger.mat', where trigger is 1:12, and only triggers 1-3
(positive polarity) and 7-9 (negative polarity) are of interest. Epochs were
400 ms long.

This generates a .csv file with the results after bootstrapping in an
"Excel-friendly" format. See moddepth_analysis_results_example.csv for sample
output.

command line usage:
$ python moddepth_analysis.py dataDir saveDir minTrials subject001 [...]

where [...] are inputs for additional subjects.

Last updated: 08/27/2014
Auditory Neuroscience Laboratory, Boston University
Contact: lennyv@bu.edu
'''

from __future__ import print_function
import os
import sys
from numpy import random
from scipy import io
from anlffr import spectral
from anlffr import bootstrap
from anlffr.utils import logger

# prints all info messages from ANLffr to stdout
logger.setLevel('INFO')

def _check_filename(inSaveName, inSaveDir):
    '''
    just checks the filenames and increments a counter after filename if it
    already exists
    '''

    counter = 0
    fullFilename = os.path.join(inSaveDir, inSaveName)

    while os.path.exists(fullFilename):
        counter = counter+1
        fullFilename = (os.path.splitext(fullFilename)[0] + '_' +
                        str(counter) + '.csv')

    return fullFilename

dataDir = sys.argv[1]
saveDir = sys.argv[2]
minTrials = int(sys.argv[3])
subjectList = sys.argv[4:]

# use a 2048 point fft, but results will only include freqs between 70-1000 the
# noise floor is determined by flipping the phase of half of the trials and
# then recomputing everything
params = spectral.generate_parameters(sampleRate=5000,
                                      nfft=2048,
                                      fpass=[70.0, 1000.0],
                                      tapers=[2, 3],
                                      noiseFloorType=['phaseFlipHalfTrials'],
                                      nDraws=100,
                                      nPerDraw=minTrials,
                                      threads=6,
                                      returnIndividualBootstrapResults=False)

# cycle through each subject, then conditions 1-3
for s in subjectList:
    for c in range(1, 4):

        loadName = {}
        print('condition: {}'.format(c))
        loadName['positive'] = s + '_S_' + str(c) + '.mat'
        loadName['negative'] = s + '_S_' + str(c+6) + '.mat'

        # open/check the save file name
        saveName = s + '_condition_' + str(c) + '.csv'
        outputFilename = _check_filename(saveName, saveDir)
        outputFile = open(outputFilename, 'w')

        try:
            combinedData = []

            # loads the positive and negative mat files for this condition (c)
            for l in loadName:

                wholeMat = io.loadmat(os.path.join(dataDir, loadName[l]))
                mat = wholeMat['data']
                sampleRateFromFile = wholeMat['sampleRate']

                assert mat.shape[1] > minTrials

                assert sampleRateFromFile == params['Fs']

                # consider a random subset of minTrials trials
                permutedTrials = random.permutation(range(mat.shape[1]))
                useTrials = permutedTrials[0:minTrials]

                # bootstrap.bootfunc takes in a list of arrays, then subsamples
                # evenly from those arrays those
                print('using {} polarity trials:\n {}'.format(l, useTrials))
                combinedData.append(mat[:, useTrials, :])

            # call the bootrapping function using mtcpca_complete
            result = bootstrap.bootfunc(spectral.mtcpca_complete,
                                        combinedData,
                                        params)

            # here is where you can change the format to better suit whatever
            # you're doing see the first outputFile.write command to see the
            # current column headers

            # there are 13 columns
            printStr = ('{0},{1},{2},{3},{4},{5},{6},{7},' +
                        '{8},{9},{10},{11},{12}\n')

            # write the column headers
            outputFile.write(printStr.format(
                'Subject Name',
                'Condition',
                'Number of Draws',
                'Trials per Draw',
                'Frequency',
                'PLV**2: bootstrapped mean',
                'PLV**2: bootstrapped variance',
                'Spectrum: bootstrapped mean',
                'Spectrum: bootstrapped variance',
                'Noise floor PLV**2: bootstrapped mean',
                'Noise floor PLV**2: bootstrapped variance',
                'Noise floor Spectrum: bootstrapped mean',
                'Noise floor Spectrum: bootstrapped variance'))

            # now write all the information to file
            for plvF in range(len(params['f'])):
                toWrite = printStr.format(
                    s,
                    c,
                    params['nDraws'],
                    params['nPerDraw'],
                    params['f'][plvF],
                    (result['mtcpcaPLV_normalPhase']
                           ['bootMean']
                           [plvF]),
                    (result['mtcpcaPLV_normalPhase']
                           ['bootVariance']
                           [plvF]
                     ),
                    (result['mtcpcaSpectrum_normalPhase']
                           ['bootMean']
                           [plvF]
                     ),
                    (result['mtcpcaSpectrum_normalPhase']
                           ['bootVariance']
                           [plvF]
                     ),
                    (result['mtcpcaPLV_phaseFlipHalfTrials']
                           ['bootMean']
                           [plvF]
                     ),
                    (result['mtcpcaPLV_phaseFlipHalfTrials']
                           ['bootVariance']
                           [plvF]
                     ),
                    (result['mtcpcaSpectrum_phaseFlipHalfTrials']
                           ['bootMean']
                           [plvF]
                     ),
                    (result['mtcpcaSpectrum_phaseFlipHalfTrials']
                           ['bootVariance']
                           [plvF]
                     )
                    )

                outputFile.write(toWrite)
            # make sure to close the file when finished
            outputFile.close()

        except IOError:
            print(('\nCannot find file: {}, skipping,' +
                   'condition {} \n').format(loadName[l],
                                             c))
            continue
        except AssertionError:
            print(('\nOnly {} trials detected in {}, ' +
                   'skipping condition {}...\n').format(mat.shape[1],
                                                        loadName[l],
                                                        c))
            continue
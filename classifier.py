import requests
import gzip
import json
import re

import sys
import os
import glob
module_path = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))

SAMPLE_PATH = os.path.join(module_path, 'samples')

try:
    # for RESTful interface to remote model
    __private_data = json.load(open(os.path.join(module_path, 'params.json'), 'r'))
except FileNotFoundError:
    # if you want to use the cloud interface, you must populate your own params.json
    # file.  Look at params.json.in for a template, which takes the following form
    __private_data = {
          "url": "http://my.av.api", # route to RESTful API interface
          "username": "username",    # Username
          "password": "password",    # password
          "version": "1.0",          # version
          "threshold": 0.10          # threshold
    }
    # you may also need to change get_score_remote and/or get_label_remote below

# for local model
from gym_malware.envs.utils.pefeatures import PEFeatureExtractor
from gym_malware.envs.utils.pefeatures2 import PEFeatureExtractor2
from sklearn.externals import joblib
feature_extractor =  PEFeatureExtractor()
feature_extractor2 =  PEFeatureExtractor2()
local_model = joblib.load(os.path.join(module_path, 'gym_malware/envs/utils/gradient_boosting.pkl') )
local_model_threshold = 0.70

class ClassificationFailure(Exception):
    pass

class FileRetrievalFailure(Exception):
    pass

def main():
  file = sys.argv[1]
  with open(file, 'rb') as infile:
      bytez = infile.read()
  label = get_label_local(bytez)


def fetch_file(sha256):
    location = os.path.join(SAMPLE_PATH, sha256)
    try:
        with open(location, 'rb') as infile:
            bytez = infile.read()
    except IOError:
        raise FileRetrievalFailure(
            "Unable to read sha256 from {}".format(location))

    return bytez

def get_available_sha256():
    sha256list = []
    for fp in glob.glob(os.path.join(SAMPLE_PATH, '*')):
        fn = os.path.split(fp)[-1]
        result = re.match(r'^[0-9a-fA-F]{64}$', fn) # require filenames to be sha256
        if result:
            sha256list.append(result.group(0))
    assert len(sha256list)>0, "no files found in {} with sha256 names".format( SAMPLE_PATH )
    return sha256list

# modify this function to git a remote API of your choice
# note that in this example, the API route expects version specification
# in addition to authentication username and password
def get_score_remote(bytez):
    try:
        response = requests.post(__private_data['url'],
                                 params={'version': __private_data['version']},
                                 auth=(__private_data['username'],
                                       __private_data['password']),
                                 headers={
                                     'Content-Type': 'application/octet-stream'},
                                 data=bytez)
    except ConnectionError:
        print("Bad route for hitting remote AV via RESTful interface. Please modify params.json (see params.json.in).")
        raise

    if not response.ok:
        raise(ClassificationFailure("Unable to get label for query"))
    json_response = response.json()
    if not 'data' in json_response or not 'score' in json_response['data']:
        raise(ClassificationFailure(
            "Can't find ['data']['score'] in response"))
    # mimic black box by thresholding here
    return json_response['data']['score']


def get_label_remote(bytez):
    # mimic black box by thresholding here
    return float( get_score_remote(bytez) >= __private_data['threshold'] )


def get_score_local(bytez):
    # extract features
    features = feature_extractor2.extract( bytez )
    # query the model
    score = local_model.predict_proba( features.reshape(1,-1) )[0,-1] # predict on single sample, get the malicious score
    return score

def get_label_local(bytez):
    # mimic black box by thresholding here
    score = get_score_local(bytez)
    label = float( get_score_local(bytez) >= local_model_threshold )
    print("score={} (hidden), label={}".format(score,label)) 
    return label

if __name__ == '__main__':
    main()
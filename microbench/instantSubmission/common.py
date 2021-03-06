import ray
import csv
import numpy as np 
import time
import argparse
import os
import ray
from termcolor import colored
import re

params=0

def get_params():
    global params
    parser = argparse.ArgumentParser()
    parser.add_argument('--WORKING_SET_RATIO', '-w', type=int, default=1)
    parser.add_argument('--OBJECT_STORE_SIZE', '-o', type=int, default=4_000_000_000)
    parser.add_argument('--OBJECT_SIZE', '-os', type=int, default=100_000_000)
    parser.add_argument('--RESULT_PATH', '-r', type=str, default="../data/dummy.csv")
    parser.add_argument('--NUM_TRIAL', '-t', type=int, default=1)
    parser.add_argument('--NUM_STAGES', '-ns', type=int, default=1)
    parser.add_argument('--NUM_WORKER', '-nw', type=int, default=60)
    parser.add_argument('--SEED', '-s', type=int, default=0)
    parser.add_argument('--LATENCY', '-l', type=float, default=0)
    args = parser.parse_args()
    params = vars(args)

    return params

def warmup(OBJECT_STORE_SIZE):
    @ray.remote(num_cpus=1)
    def producer(n):
        return np.random.randint(2147483647, size=(OBJECT_STORE_SIZE//(8*n*2)))

    @ray.remote(num_cpus=1)
    def consumer(obj):
        return True
    res = []
    n =2 
    for i in range(n):
        res.append(consumer.remote(producer.remote(n)))
    ray.get(res)
    del res
    time.sleep(1)

def get_num_spilled_objs():
    os.system('ray memory --stats-only > /tmp/ray/spilllog')
    with open("/tmp/ray/spilllog", 'r') as file:
        lines = file.readlines()

        num = 0
        size = 0
        for line in lines:
            if line.find("Spilled") != -1:
                line = line.split()
                idx = line.index('Spilled')
                num += int(line[idx+3])
                size += int(line[idx+1])
        return num,size

def run_test(benchmark):
    OBJECT_STORE_SIZE = params['OBJECT_STORE_SIZE'] 
    OBJECT_SIZE = params['OBJECT_SIZE'] 
    WORKING_SET_RATIO = params['WORKING_SET_RATIO']
    RESULT_PATH = params['RESULT_PATH']
    NUM_TRIAL = params['NUM_TRIAL']
    NUM_WORKER = params['NUM_WORKER']
    OBJECT_STORE_BUFFER_SIZE = 50_000_000 #this value is to add some space in ObjS for nprand metadata and ray object metadata

    debugging = False
    ray_time = []
    num_spilled_objs = 0
    spilled_size = 0

    if 'dummy' in RESULT_PATH:
        debugging = True

    for i in range(NUM_TRIAL):
        ray.init(object_store_memory=OBJECT_STORE_SIZE+OBJECT_STORE_BUFFER_SIZE , num_cpus = NUM_WORKER)
        if not debugging:
            warmup(OBJECT_STORE_SIZE)

        ray_time.append(benchmark())
        num,size = get_num_spilled_objs()
        num_spilled_objs += num
        spilled_size += size

        print(ray_time, num, size)
        ray.shutdown()

    if not debugging:
        data = [np.std(ray_time), np.var(ray_time), WORKING_SET_RATIO, OBJECT_STORE_SIZE, OBJECT_SIZE, sum(ray_time)/NUM_TRIAL, num_spilled_objs//NUM_TRIAL, spilled_size//NUM_TRIAL]
        with open(RESULT_PATH, 'a', encoding='UTF-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(data)

    print(ray_time)
    print(colored(sum(ray_time)/NUM_TRIAL,'green'))

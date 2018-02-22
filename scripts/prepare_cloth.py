import numpy as np
import cv2
from matplotlib import pyplot as plt
import pickle
import time
from pathlib import Path
import codecs
import math
import multiprocessing as mp
# from skimage.util import view_as_blocks
import copy
# from sklearn.cluster import KMeans
import os
from utility import *

def prepare_images_for_cloth(anchor_dict):
    for video_name, anchor_group in anchor_dict.items():
        ## find pos cluster
        fid2person = {}
        fid2index = {}
        for i, anchor_person in enumerate(anchor_group):
            pos_type = {}
            for j, p in enumerate(anchor_person):
                if not p['fake']:
                    if not p['type'] in pos_type:
                        fid2person[p['fid']] = p
                        fid2index[p['fid']] = (i, len(pos_type))
                        pos_type[p['type']] = 0
        
        video_path = '../data/videos/' + video_name + '.mp4'
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if not ret:
            print("Video %s does not exist!!!" % video_path)
            return 
        fid = 1

        W  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        ret = True
        cnt = 0
        while cnt != len(fid2person):
            ret, frame = cap.read()
            if fid in fid2person:
                p = fid2person[fid]
                index = fid2index[fid]
                cnt += 1
                x1 = int(p['bbox']['bbox_x1'] * W)
                y1 = int(p['bbox']['bbox_y1'] * H)
                x2 = int(p['bbox']['bbox_x2'] * W)
                y2 = int(p['bbox']['bbox_y2'] * H)
                ## set crop window
                crop_w = (x2 - x1) * 2
                crop_h = crop_w * 2
                X1 = int((x1 + x2) / 2 - crop_w / 2)
                X2 = X1 + crop_w
                Y1 = int((y1 + y2) / 2 - crop_h / 3)
                Y2 = Y1 + crop_h
                ## adjust box size by image boundary
                crop_x1 = max(0, X1)
                crop_x2 = min(W-1, X2)
                crop_y1 = max(0, Y1)
                crop_y2 = min(H-1, Y2)
                
                filename = '../data/cloth/' + video_name + '_' + str(index[0]) + '_' + str(index[1]) + '.jpg'
                cv2.imwrite(filename, frame[crop_y1:crop_y2+1, crop_x1:crop_x2+1, :])
            fid += 1
        break

def prepare_images_for_cloth2(video_name, anchor_group):

    ## collect face by fid
    fid2person = {}
    dist_matrix = [] 
    for i, anchor_person in enumerate(anchor_group):
        for j, p in enumerate(anchor_person):
            if not p['fake']:
                if not p['fid'] in fid2person:
                    fid2person[p['fid']] = []
                p['index'] = (i, j)
                fid2person[p['fid']].append(p)
        dist_matrix.append([])

    video_path = '../data/videos/' + video_name + '.mp4'
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if not ret:
        print("Video %s does not exist!!!" % video_path)
        return 
    fid = 1

    W  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cnt = 0
    while cnt != len(fid2person):
        ret, frame = cap.read()
        if fid in fid2person:
            for p in fid2person[fid]:
                index = p['index']
                cnt += 1
                x1 = int(p['bbox']['bbox_x1'] * W)
                y1 = int(p['bbox']['bbox_y1'] * H)
                x2 = int(p['bbox']['bbox_x2'] * W)
                y2 = int(p['bbox']['bbox_y2'] * H)
                ## set crop window
                crop_w = (x2 - x1) * 2
                crop_h = crop_w * 2
                X1 = int((x1 + x2) / 2 - crop_w / 2)
                X2 = X1 + crop_w
                Y1 = int((y1 + y2) / 2 - crop_h / 3)
                Y2 = Y1 + crop_h
                ## adjust box size by image boundary
                crop_x1 = max(0, X1)
                crop_x2 = min(W-1, X2)
                crop_y1 = max(0, Y1)
                crop_y2 = min(H-1, Y2)
                ## compare histogram to find obstacle
                y_med = int((y2 + crop_y2) / 2)
                hist_top = cv2.calcHist([frame[y2:y_med, crop_x1:crop_x2+1, :]], [0, 1, 2], None, [16, 16, 16], [0, 255, 0, 255, 0, 255])
                hist_bottom = cv2.calcHist([frame[y_med:crop_y2+1, crop_x1:crop_x2+1, :]], [0, 1, 2], None, [16, 16, 16], [0, 255, 0, 255, 0, 255])
                dist = np.linalg.norm(hist_top - hist_bottom)
                dist_matrix[index[0]].append(dist)
                cropped = frame[crop_y1:crop_y2+1, crop_x1:crop_x2+1, :]
                text = '{0:.3f}'.format(dist)
                cv2.rectangle(cropped, (0, 0), (cropped.shape[1]-1, 30), color=(255,255,255), thickness=-1)
                cv2.putText(cropped, text, (0,25), cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.7, color=(0,0,0), thickness=2)
                p['frame'] = cropped
        fid += 1
    cap.release()

    ## find the frames not occludded
    NUM_PER_ANCHOR = 5
    for i, anchor_person in enumerate(anchor_group):
        top_sim = np.argsort(dist_matrix[i])
        num_anchor = min(NUM_PER_ANCHOR, len(anchor_person))
        for j in range(num_anchor):
            filename = '../data/cloth/' + video_name + '_' + str(i) + '_' + str(j) + '.jpg'
            cv2.imwrite(filename, anchor_person[top_sim[j]]['frame'])


def solve_single_video(video_name, anchor_group):
    prepare_images_for_cloth2(video_name, anchor_group)

def solve_thread(video_list, tmp_dict_path, thread_id):
    print("Thread %d start computing..." % (thread_id))
    
    ## load dict
    anchor_dict = pickle.load(open('../data/anchor_dict_test.pkl', 'rb'))
#     res_dict = {}
    
    for i in range(len(video_list)):
        video_name = video_list[i]
        print("Thread %d start %dth video: %s" % (thread_id, i, video_name))
        if video_name in anchor_dict:
            solve_single_video(video_name, anchor_dict[video_name])

#         res_dict[video_name] = res
#         if i % 100 == 0:
#             pickle.dump(res_dict, open(tmp_dict_path, "wb" ))
            
#         pickle.dump(res_dict, open(tmp_dict_path, "wb" ))
    print("Thread %d finished computing..." % (thread_id))

def solve_parallel(video_list_path, res_dict_path=None, nthread=16, use_process=True):
    video_list = open(video_list_path).read().split('\n')
    
    ## remove exist video
#     dict_file = Path(res_dict_path)
#     if dict_file.is_file():
#         res_dict = pickle.load(open(res_dict_path, "rb" ))
#         video_list = [video for video in video_list if video not in res_dict]
#     else:
#         res_dict = {}

    num_video = len(video_list)
    print(num_video)
    if num_video == 0:
        return 
    if num_video <= nthread:
        nthread = num_video
        num_video_t = 1
    else:
        num_video_t = math.ceil(1. * num_video / nthread)
    print(num_video_t)
    
    tmp_dict_list = []
    for i in range(nthread):
        tmp_dict_list.append('../tmp/anchor_dict_' + str(i) + '.pkl')

    if use_process:
        ctx = mp.get_context('spawn')
    thread_list = []
    for i in range(nthread):
        if i != nthread - 1:
            video_list_t = video_list[i*num_video_t : (i+1)*num_video_t]
        else:
            video_list_t = video_list[i*num_video_t : ]
        if use_process:
            t = ctx.Process(target=solve_thread, args=(video_list_t, tmp_dict_list[i], i,))
        else:
            t = threading.Thread(target=solve_thread, args=(video_list_t, tmp_dict_list[i], i,))
            t.setDaemon(True)
        thread_list.append(t)
    
    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()
    
#     for path in tmp_dict_list:
#         dict_file = Path(path)
#         if not dict_file.is_file():
#             continue
#         res_dict_tmp = pickle.load(open(path, "rb" ))
#         res_dict = {**res_dict, **res_dict_tmp}
    
#     pickle.dump(res_dict, open(res_dict_path, "wb" ))  
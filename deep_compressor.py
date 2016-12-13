import tensorflow as tf
import numpy as np
import math
import glob
import msssim
from scipy import misc

from frame_interpolator import *

import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt

def normalize_frames(frames, medians):
    diff = frames - medians
    thresh = 1
    mask = np.all((np.abs(diff)>thresh), axis = 3, keepdims=True)
    mask = np.tile(mask,[1,1,1,3])
    # return mask*frames;
    return diff

def unnormalize_frames(frames, medians):
    # frames = np.maximum(np.zeros(frames.shape), frames)
    # thresh = 8
    # mask = np.all((np.abs(frames)<=thresh), axis = 3, keepdims=True)
    # mask = np.tile(mask,[1,1,1,3])
    # return mask*medians + np.logical_not(mask)*frames;
    return frames + medians


def compile_input_data(saved_frames):
    frame_shape = saved_frames[1,:,:,:].shape
    frame_size = saved_frames[1,:,:,:].size
    n_frames = saved_frames.shape[0]

    before_frames = saved_frames[0:-1,:,:,:]
    after_frames = saved_frames[1:,:,:,:]

    oned_frames = np.reshape(saved_frames, [-1, frame_size])
    median_frame = np.median(oned_frames, axis=0)
    median_frame = np.reshape(median_frame, frame_shape)

    medians = np.tile(median_frame, [n_frames-1,1,1,1])

    # before_norm = 255 - before_frames
    # after_norm = 255 - after_frames
    before_norm = normalize_frames(before_frames, medians)
    after_norm = normalize_frames(after_frames, medians)

    training_inputs = np.concatenate((before_norm, after_norm), axis=3)

    return (training_inputs, medians)

def load_video(input_video_dir):
    image_paths = glob.glob(input_video_dir + "/*.png")
    image_paths.sort()

    frames = []

    downsample_factor = 2
    # load data into train_inputs/targets
    for i in range(0,len(image_paths)):
        frame = np.array(misc.imread(image_paths[i]))
        frame = frame[::downsample_factor,::downsample_factor,:]

        frames.append(frame)

    frames = np.array(frames)

    frames_to_save = frames[::2,:,:,:]
    training_targets = frames[1:-1:2,:,:,:]
    training_inputs,medians = compile_input_data(frames_to_save)
    #training_targets = -(training_targets - medians)
    #training_targets = 255 - training_targets
    training_targets = normalize_frames(training_targets, medians)

    return {"frames_to_save": frames_to_save, "training_inputs": training_inputs,
     "training_targets": training_targets}


def network_trainer(training_inputs, training_targets, sess):

    img_width = training_targets[0,:,:,:].shape[1]
    fi = frame_interpolator([None,img_width,img_width,3])

    learning_rate = 0.01
    optimizer = tf.train.AdagradOptimizer(learning_rate).minimize(fi['loss'])

    # sess = tf.Session(config=tf.ConfigProto(log_device_placement=True))
    # sess = tf.Session()
    sess.run(tf.initialize_all_variables())

    # Fit all the training data
    n_epochs = 150
    n_examples = training_inputs.shape[0]
    print(n_examples)
    batch_size = 7
    for epoch_i in range(n_epochs):
        shuffled_inds = np.random.permutation(n_examples)
        for batch_i in range(n_examples // batch_size):
            batch_inds = range(batch_i*batch_size, (batch_i+1)*batch_size)
            batch_inds = shuffled_inds[batch_inds]
            batch_xs = training_inputs[batch_inds,:,:,:]
            batch_ys = training_targets[batch_inds,:,:,:]
            #print(batch_xs.shape, batch_ys.shape)
            # fig, axs = plt.subplots(3, 1, figsize=(12, 8))
            # axs[0].imshow(batch_xs[0,:,:,0:3])
            # axs[1].imshow(batch_xs[0,:,:,3:])
            # axs[2].imshow(batch_ys[0,:,:,:])
            # plt.show()

            sess.run(optimizer, feed_dict={fi['x']: batch_xs, fi['y']: batch_ys})

        print(epoch_i, sess.run(fi['loss'], feed_dict={fi['x']: batch_xs, fi['y']: batch_ys}))

    return fi

def decompress(saved_frames, trained_net, sess):
    # compute median
    (network_inputs, medians) = compile_input_data(saved_frames)
    network_outputs = sess.run(trained_net['yhat'], 
        feed_dict={trained_net['x']: network_inputs})
    #output_frames = network_outputs + medians
    import scipy.io
    scipy.io.savemat('networkout.mat', mdict={'network_outputs': network_outputs,
        'medians':medians})

    output_frames = unnormalize_frames(network_outputs, medians)
    return output_frames


def main():
    video_data = load_video('./SampleVid')
    sess = tf.Session()
    trained_net = network_trainer(video_data['training_inputs'], 
        video_data['training_targets'], sess)
    
    saver = tf.train.Saver()
    save_path = saver.save(sess, "saved_net.ckpt")
    print("Model saved in file: %s" % save_path)
    
    output_frames = decompress(video_data['frames_to_save'],
        trained_net, sess)

    img_width = output_frames[1,:,:,:].shape[1]
    fig, axs = plt.subplots(3, 4, figsize=(12, 8))
    for plot_i, example_i in enumerate([7, 89, 91, 100]):
        axs[0][plot_i].imshow((np.reshape(0.5*video_data['frames_to_save'][example_i,:,:,:] + 0.5*video_data['frames_to_save'][example_i+1,:,:,:], (img_width,img_width,3)))/255)
        axs[1][plot_i].imshow((np.reshape(output_frames[example_i, ...], (img_width, img_width, 3)))/255)
        axs[2][plot_i].imshow((np.reshape(video_data['training_targets'][example_i,:,:,:], (img_width, img_width, 3)))/255)

    plt.show()
    fig.savefig('jomama.pdf')








if __name__ == '__main__':
    main()
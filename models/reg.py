""" This module implement a toy task: linear regression """
# __Author__ == "Haowen Xu"
# __Data__ == "04-08-2018"

import numpy as np
import math
import os

import tensorflow as tf
import tensorflow.contrib.slim as slim

import utils
from dataio.dataset import Dataset
from models.basic_model import Basic_model

logger = utils.get_logger()

class Reg(Basic_model):
    '''
    Public variables (all task models should have these public variables):
        self.extra_info
        self.checkpoint_dir
        self.best_performance
        self.test_dataset
    '''

    def __init__(self, config, exp_name='new_exp'):
        super(Reg, self).__init__(config, exp_name)
        self.reset()
        self._load_datasets()
        self._build_placeholder()
        self._build_graph()
        self.reward_baseline = None
        self.improve_baseline = None

    def _load_datasets(self):
        config = self.config
        train_ctrl_data_file = os.path.join(config.data_dir, config.train_ctrl_data_file)
        train_task_data_file = os.path.join(config.data_dir, config.train_task_data_file)
        valid_ctrl_data_file = os.path.join(config.data_dir, config.valid_ctrl_data_file)
        valid_task_data_file = os.path.join(config.data_dir, config.valid_task_data_file)
        test_data_file = os.path.join(config.data_dir, config.test_data_file)
        self.train_ctrl_dataset = Dataset()
        self.train_ctrl_dataset.load_npy(train_ctrl_data_file)
        self.valid_ctrl_dataset = Dataset()
        self.valid_ctrl_dataset.load_npy(valid_ctrl_data_file)
        self.train_task_dataset = Dataset()
        self.train_task_dataset.load_npy(train_task_data_file)
        self.valid_task_dataset = Dataset()
        self.valid_task_dataset.load_npy(valid_task_data_file)
        self.test_dataset = Dataset()
        self.test_dataset.load_npy(test_data_file)

    def reset(self):
        """ Reset the model """
        # TODO(haowen) The way to carry step number information should be
        # reconsiderd
        self.step_number = [0]
        self.previous_mse_loss = [0] * self.config.num_pre_loss
        self.previous_l1_loss = [0] * self.config.num_pre_loss
        self.previous_valid_loss = [0] * self.config.num_pre_loss
        self.previous_train_loss = [0] * self.config.num_pre_loss
        self.mag_mse_grad = 0
        self.mag_l1_grad = 0

        # to control when to terminate the episode
        self.endurance = 0
        # The bigger, the better. In this case, performance is negative loss.
        # Naming it as performance in order to be compatible with other tasks.
        self.best_performance = -1e10
        self.collapse = False
        self.improve_baseline = None

    def _build_placeholder(self):
        x_size = self.config.dim_input_task
        with self.graph.as_default():
            self.x_plh = tf.placeholder(shape=[None, x_size], dtype=tf.float32)
            self.y_plh = tf.placeholder(shape=[None], dtype=tf.float32)

    def _build_graph(self):
        y_size = self.config.dim_output_task
        lr = self.config.lr_task

        with self.graph.as_default():
            # ----quadratic equation----
            #  ---first order---
            x_size = self.config.dim_input_task
            initial = tf.random_normal(shape=[x_size, 1], stddev=0.1, seed=1)
            w1 = tf.Variable(initial)
            sum1 = tf.matmul(self.x_plh, w1)

            #  ---second order---
            initial = tf.random_normal(shape=[x_size, x_size], stddev=0.01,
                                       seed=1)
            w2 = tf.Variable(initial)
            xx = tf.matmul(tf.reshape(self.x_plh, [-1, x_size, 1]),
                           tf.reshape(self.x_plh, [-1, 1, x_size]))
            sum2 = tf.matmul(tf.reshape(xx, [-1, x_size*x_size]),
                             tf.reshape(w2, [x_size*x_size, 1]))

            # NOTE(Haowen): Divide by 10 is important here to promise
            # convergence. It is some kind of cheating but we think it is fine
            # as a demo task.
            self.pred = sum1 + sum2 / 10

            # Only for debug
            self.w1 = w1
            self.w2 = w2

            # define loss
            self.loss_mse = tf.reduce_mean(tf.square(tf.squeeze(self.pred)
                                                     - self.y_plh))

            # NOTE(Haowen): Somehow the l1 regularizers provided by tf
            # provide a better performance than self-designed regularizers
            # showing in the flowing 6 lines.

            #self.loss_l1 = self.config.lambda_task * (
            #    tf.reduce_sum(tf.reduce_sum(tf.abs(w2)))\
            #    + tf.reduce_sum(tf.reduce_sum(tf.abs(w1))))

            tvars = tf.trainable_variables()
            l1_regularizer = tf.contrib.layers.l1_regularizer(
                scale=self.config.lambda_task, scope=None)
            self.loss_l1 = tf.contrib.layers.apply_regularization(
                l1_regularizer, tvars)
            self.loss_total = self.loss_mse + self.loss_l1

            # ----Define update operation.----
            optimizer = tf.train.AdamOptimizer(lr)
            mse_gvs = optimizer.compute_gradients(self.loss_mse, tvars)
            l1_gvs = optimizer.compute_gradients(self.loss_l1, tvars)
            total_gvs = optimizer.compute_gradients(self.loss_total, tvars)
            self.update_mse = optimizer.apply_gradients(mse_gvs)
            self.update_l1 = optimizer.apply_gradients(l1_gvs)
            self.update_total = optimizer.apply_gradients(total_gvs)
            self.update = [self.update_mse, self.update_l1]

            self.init = tf.global_variables_initializer()
            self.saver = tf.train.Saver()
            self.mse_grad = [grad for grad, _ in mse_gvs]
            self.l1_grad = [grad for grad, _ in l1_gvs]

    def valid(self, dataset=None):
        if not dataset:
            if self.config.args.task_mode == 'train':
                dataset = self.valid_ctrl_dataset
            elif self.config.args.task_mode == 'test':
                dataset = self.valid_task_dataset
            elif self.config.args.task_mode == 'baseline':
                dataset = self.valid_task_dataset
            else:
                logger.exception('Unexcepted task_mode: {}'.\
                                format(self.config.args.task_mode))
        data = dataset.next_batch(dataset.num_examples)
        x = data['input']
        y = data['target']
        feed_dict = {self.x_plh: x, self.y_plh: y}
        fetch = [self.loss_mse, self.pred, self.y_plh]
        [loss_mse, pred, gdth] = self.sess.run(fetch, feed_dict=feed_dict)
        return loss_mse, pred, gdth

    def response(self, action):
        """ Given an action, return the new state, reward and whether dead

        Args:
            action: one hot encoding of actions

        Returns:
            state: shape = [dim_input_ctrl]
            reward: shape = [1]
            dead: boolean
        """
        if self.config.args.task_mode == 'train':
            dataset = self.train_ctrl_dataset
        elif self.config.args.task_mode == 'test':
            dataset = self.train_task_dataset
        elif self.config.args.task_mode == 'baseline':
            dataset = self.train_task_dataset
        else:
            logger.exception('Unexcepted mode: {}'.\
                             format(self.config.args.task_mode))
        data = dataset.next_batch(self.config.batch_size)

        sess = self.sess
        x = data['input']
        y = data['target']
        feed_dict = {self.x_plh: x, self.y_plh: y}

        a = np.argmax(np.array(action))
        sess.run(self.update[a], feed_dict=feed_dict)

        fetch = [self.loss_mse, self.loss_l1, self.mse_grad, self.l1_grad]
        loss_mse, loss_l1, mse_grad, l1_grad = sess.run(fetch, feed_dict=feed_dict)
        valid_loss, _, _ = self.valid()
        train_loss = loss_mse

        # ----Update state.----
        self.previous_mse_loss = self.previous_mse_loss[1:] + [loss_mse.tolist()]
        self.previous_l1_loss = self.previous_l1_loss[1:] + [loss_l1.tolist()]
        self.step_number[0] += 1
        self.previous_valid_loss = self.previous_valid_loss[1:]\
            + [valid_loss.tolist()]
        self.previous_train_loss = self.previous_train_loss[1:]\
            + [train_loss.tolist()]
        self.mag_mse_grad = self.get_grads_magnitude(mse_grad)
        self.mag_l1_grad = self.get_grads_magnitude(l1_grad)

        # Public variable
        self.extra_info = {'valid_loss': self.previous_valid_loss[-1],
                           'train_loss': self.previous_train_loss[-1]}

        reward = self.get_step_reward()
        # ----Early stop and record best result.----
        dead = self.check_terminate()
        state = self.get_state()
        return state, reward, dead

    def check_terminate(self):
        # TODO(haowen)
        # Episode terminates on two condition:
        # 1) Convergence: valid loss doesn't improve in endurance steps
        # 2) Collapse: action space collapse to one action (not implement yet)

        # Return True if the training should stop, otherwise return False
        step = self.step_number[0]
        if step % self.config.valid_frequency_task == 0:
            self.endurance += 1
            loss, _, _ = self.valid()
            if -loss > self.best_performance:
                self.best_step = self.step_number[0]
                self.best_performance = -loss
                self.endurance = 0
                if not self.config.args.task_mode == 'train':
                    self.save_model(step, mute=True)

        if step > self.config.max_training_step:
            return True
        if self.config.stop_strategy_task == 'exceeding_endurance' and \
                self.endurance > self.config.max_endurance_task:
            return True
        return False

    def get_step_reward(self):
        # TODO(haowen) Use the decrease of validation loss as step reward
        if self.improve_baseline is None:
            # ----First step, nothing to compare with.----
            improve = 0.1
        else:
            improve = (self.previous_valid_loss[-2] - self.previous_valid_loss[-1])

        # TODO(haowen) Try to use sqrt function instead of sign function
        if self.improve_baseline is None:
            self.improve_baseline = improve
        decay = self.config.reward_baseline_decay
        self.improve_baseline = decay * self.improve_baseline\
            + (1 - decay) * improve

        value = math.sqrt(abs(improve) / (abs(self.improve_baseline) + 1e-5))
        #value = abs(improve) / (abs(self.improve_baseline) + 1e-5)
        value = min(value, self.config.reward_max_value)
        return math.copysign(value, improve) * self.config.reward_step_ctrl

    def get_final_reward(self):
        '''
        Return:
            reward: real reward
            adv: advantage, subtract the baseline from reward and then normalize it
        '''
        assert self.best_performance > -1e10 + 1
        loss_mse = -self.best_performance
        reward = self.config.reward_c / loss_mse

        # Calculate baseline
        if self.reward_baseline is None:
            self.reward_baseline = reward
        else:
            decay = self.config.reward_baseline_decay
            self.reward_baseline = decay * self.reward_baseline\
                + (1 - decay) * reward

        # Calculate advantage
        adv = reward - self.reward_baseline
        adv = min(adv, self.config.reward_max_value)
        adv = max(adv, -self.config.reward_max_value)
        return reward, adv

    def get_state(self):
        abs_diff = []
        rel_diff = []
        if self.improve_baseline is None:
            ib = 1
        else:
            ib = self.improve_baseline

        # relative difference between valid_loss and train_loss:
        # we only consider the latest step
        v = self.previous_valid_loss[-1]
        t = self.previous_train_loss[-1]
        abs_diff = v - t
        if t > 1e-6:
            rel_diff = (v - t) / t
        else:
            rel_diff = 0
        state0 = rel_diff

        # normalized baseline improvement
        state1 = 1 + math.log(abs(ib) + 1e-5) / 12

        # normalized mse loss
        mse_loss = self.previous_mse_loss[-1]
        state2 = min(1, mse_loss / 20) - 0.5

        # normalized l1 loss
        l1_loss = self.previous_l1_loss[-1]
        state3 = l1_loss - 1

        # difference between magnitude of mse gradient and magnitude of l1
        # gradient
        state4 = self.mag_mse_grad - self.mag_l1_grad

        state = [state0, state1, state2, state3, state4]

        return np.array(state, dtype='f')

class controller_designed():
    def __init__(self, config=None):
        self.step = 0
        self.config = config

    def sample(self, state):
        self.step += 1
        action = [0, 0]
        action[self.step % 2] = 1
        return np.array(action)

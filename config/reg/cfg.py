import os, sys
import socket
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, root_path)

def get_cfg():
    return Config()

class Config():
    def __init__(self):
        self.hostname = socket.gethostname()
        # Environment & Path
        self.exp_dir = root_path
        self.data_dir = os.path.join(self.exp_dir, 'data')
        self.task = 'reg'
        self.model_dir = 'ckpts'

        # Data
        self.train_ctrl_data_file = 'reg/train_ctrl.npy'
        self.valid_ctrl_data_file = 'reg/valid_ctrl.npy'
        self.train_task_data_file = 'reg/train_task.npy'
        self.valid_task_data_file = 'reg/valid_task.npy'
        self.test_data_file = 'reg/test.npy'
        self.num_sample_train_ctrl = 200
        self.num_sample_valid_ctrl = 200
        self.num_sample_train_task = 200
        self.num_sample_valid_task = 200
        self.num_sample_test = 200
        self.mean_noise = 0
        self.var_noise = 2

        # Task model
        self.dim_input_task = 16
        self.dim_output_task = 1
        self.lambda_task = 0.2

        # Training task model
        self.batch_size = 200
        self.lr_task = 0.0005
        self.valid_frequency_task = 10
        # options for `stop_strategy_task` are: exceeding_endurance,
        # exceeding_total_steps
        #self.stop_strategy_task = 'exceeding_total_steps'
        self.stop_strategy_task = 'exceeding_endurance'
        self.max_endurance_task = 100
        self.max_training_step = 20000

        # Controller
        self.controller_model_name = '2layer_logits_clipping'
        # "How many recent training steps will be recorded"
        self.num_pre_loss = 2

        self.dim_input_ctrl = 5
        self.dim_hidden_ctrl = 16
        self.dim_output_ctrl = 2
        self.reward_baseline_decay = 0.8
        self.reward_c = 20000
        # Set an max step reward, in case the improvement baseline is too small
        # and cause huge reward.
        self.reward_max_value = 20
        # TODO check out what this hp do
        self.reward_step_ctrl = 1
        self.logit_clipping_c = 2

        # Training controller
        self.lr_ctrl = 0.001
        self.total_episodes = 400
        self.update_frequency_ctrl = 1
        self.save_frequency_ctrl = 50
        self.max_endurance_ctrl = 50
        self.rl_method = 'reinforce'
        self.epsilon_start_ctrl = 0.5
        self.epsilon_end_ctrl = 0.1
        self.epsilon_decay_steps_ctrl = 1

    def print_config(self, logger):
        for key, value in vars(self).items():
            logger.info('{}:: {}'.format(key, value))

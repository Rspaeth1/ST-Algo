import torch
import torch.nn as nn
import torch.optim as optim
import os
import math
from concurrent.futures import ThreadPoolExecutor

import main

class ParamOptimizerNet(nn.Module):
    def __init__(self, param_keys, filepath=None):
        super(ParamOptimizerNet, self).__init__()
        self.param_keys = list(param_keys)
        self.epoch_print_freq = 1 / 10  # Print every 10 epochs
        self.loaded = False

        # Parameters to optimize
        self.params = nn.Parameter(torch.zeros(len(param_keys)))  # Learnable mean values
        self.log_std_head = nn.Parameter(torch.full((len(param_keys),), -1.0))  # Log std for sampling
        self.scale_params = {'exitbars': (1, 9), 'mktcap1': (-4, 4), 'mktcap2': (-4, 4), 'mktcap3': (-4, 4), 'mktcap4': (-4, 4), 'pricentile1': (0,1), 'confidence_threshold': (0,100), 'exit_threshold': (0,100)}

        
        # Load model
        if filepath and os.path.exists(filepath):
            print(f"Loading model {filepath}")
            load_model(self, filepath=filepath)
            self.loaded = True


    def forward(self):
        """Returns the current mean parameter set and log standard deviations"""
        means = torch.sigmoid(self.params) * 200 - 100  # Scale to [-100, 100]
        
        # scale certain parameters differently
        for key, value in self.scale_params.items():
            if key in self.param_keys:
                idx = self.param_keys.index(key)
                means[idx] = torch.sigmoid(self.params[idx]) * (value[1] + abs(value[0])) + value[0]
        
        log_stds = self.log_std_head  # Log standard deviations
        return means, log_stds

    
       
    def train_nn(self, num_generations=100, sigma=.1, alpha=.01):
        self.train()
        best_reward = float("-inf")
        best_params = None

        for generation in range(num_generations):
            noise = torch.randn_like(self.params) * sigma
            params_plus = self.get_params() + noise
            params_minus = self.get_params() - noise
      
            param_dict_plus = {key: val.item() for key, val in zip(self.param_keys, params_plus)}
            param_dict_minus = {key: val.item() for key, val in zip(self.param_keys, params_minus)}
      
            reward_plus = self.get_reward(param_dict_plus)
            reward_minus = self.get_reward(param_dict_minus)
      
            reward = (reward_plus - reward_minus) / (2 * sigma)
            self.update_params(noise, reward, sigma, alpha)
      
            # Track best parameters
            if reward > best_reward:
                best_reward = reward
                best_params = param_dict_plus
                save_model(self, best_params, best_reward, generation + 1)
      
            print(f"Generation {generation + 1}/{num_generations}, Reward: {reward:.4f}, Best Reward: {best_reward:.4f}")
      
        print("Training completed.")
        
    def get_reward(self, param_dict):
        # Evaluate the portfolio value for sampled parameters
        trials = 1
        total_profit = 0
        average_perc = 0
        std_perc = 0
        num_trades = 0
        runs = 0
        runs_finished = 0

        for i in range(trials):
            results = main.backtest(param_dict=param_dict)
            total_profit += results['total']
            average_perc += results['mean']
            std_perc += results['std']
            num_trades += results['num_trades']
            runs += results['runs_traded']
            runs_finished += results['runs_finished']
            
        average_perc /= trials
        std_perc /= trials
        
        #compute reward by incentivizing trading and profits
        #profit_reward = (total_profit + runs*10000) / (runs*10000 + 1)
        profit_reward = total_profit/1000
        #profit_reward += average_perc*10
        
        #encourage trading
        #inactivity_penalty = (runs_finished / (runs + 1))/2 #avoid division by 0
        inactivity_penalty = max(0,(3 - num_trades))
        
        #encourage smaller std
        std_penalty = std_perc
        
        if math.isnan(std_penalty):
            print("Std was NaN, setting 0")
            std_penalty = 0
        
        if math.isnan(profit_reward):
            print("Profit was NaN, setting penalty")
            profit_reward = 0
        
        if math.isnan(inactivity_penalty):
            print("Inactivity was NaN, setting penalty")
            inactivity_penalty = 0
        
        reward = profit_reward - inactivity_penalty - std_penalty
        
        if math.isnan(reward):
            print("Reward was NaN, setting penalty")
            reward = 0
        
        print(f"Profit Reward: {profit_reward}, Inactivity Penalty: {inactivity_penalty}, Std Penalty: {std_penalty}, Reward: {reward}")
        
        return reward
    
    def get_params(self):
        self.eval()
        
        """Samples parameters using the learned distribution"""
        means, log_stds = self.forward()
        stds = torch.exp(log_stds)  # Convert log std to std deviation
        sampled_params = means + stds * torch.randn_like(means)  # Sample using normal distribution
   
        return sampled_params

    def update_params(self, noise, reward, sigma=0.1, alpha=0.01):
        """Updates parameters using Evolution Strategies (gradient-free)"""
        self.params.data += alpha * reward * noise / (sigma + 1e-8)


#model methods

def save_model(model, best_params, best_reward, generations_trained, filepath="nn_checkpoint.pth"):
    # Convert tensor parameters to floats
    best_params_clean = {key: float(value) for key, value in best_params.items()}
    
    # Save the PyTorch model checkpoint
    checkpoint = {
        'model_state_dict': model.state_dict(),  # Save model parameters
        'param_keys': model.param_keys,  # Save parameter names
        'best_params': best_params_clean,  # Save best parameters as float dict
        'best_reward': best_reward,  # Save best reward achieved
        'generations_trained': generations_trained  # Save how many generations trained
    }
    
    torch.save(checkpoint, filepath)
    print(f"Model saved to {filepath} - Best Reward: {best_reward:.4f}")
    
    # Save the best parameters to a text file
    param_filepath = "Net_Params.txt"
    with open(param_filepath, "w") as fh:
        fh.write("params = {\n")
        for key, value in best_params_clean.items():
            fh.write(f"    '{key}': {value},\n")
        fh.write("}\n")
    
    print(f"Best parameters saved to {param_filepath}")
        
def load_model(model, optimizer=None, filepath="nn_checkpoint.pth"):
    checkpoint = torch.load(filepath)
    
    #load model state
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"Model loaded from {filepath}")
    
    #optionally load optimizer state
    if optimizer is not None:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        print("Optimizer state loaded")
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from pandas_plink import read_plink
from pysnptools.snpreader import Bed
import matplotlib.pyplot as plt
import seaborn as sns
import visualize_data as vd
import math
import csv
import os

epochs = 50
batch_size = 1
learning_rate = 0.0003
l1_penalties = [0.001, 0.01, 0.1] # coefficient of penalty of weights
val_size = 0.2
k = 3 # k-fold cross validation

directory = 'Models/lasso_firstsim/'

# Load data
'''
(bim, fam, bed) = read_plink('data/ALL_1000G_phase1integrated_v3_impute/genotypes_genome_hapgen.controls')
genotype_df = bed.compute().T
genotype_tensor = 2-torch.tensor(genotype_df)
'''
genotype_tensor = torch.zeros(100,50)

phenotype_tensor = torch.zeros(genotype_tensor.shape[0]) #TODO

dataset = torch.cat((genotype_tensor,phenotype_tensor.reshape(phenotype_tensor.shape[0],1)),dim=1)

n_SNPs = dataset.shape[1]-1
n_individuals = dataset.shape[0]

def r_correlation(tensor1, tensor2):
    if tensor1.shape != tensor2.shape:
        raise ValueError("Tensors must have the same shape")
    tensor1_mean = torch.mean(tensor1)
    tensor2_mean = torch.mean(tensor2)
    tensor1_centered = tensor1 - tensor1_mean
    tensor2_centered = tensor2 - tensor2_mean
    correlation = torch.sum(tensor1_centered * tensor2_centered) / (torch.sqrt(torch.sum(tensor1_centered ** 2)) * torch.sqrt(torch.sum(tensor2_centered ** 2)))
    return correlation.item()

def train_test_split(X, y, test_size=val_size, random_state=None):
    # Set the seed for reproducibility
    if random_state is not None:
        torch.manual_seed(random_state)

    # Shuffle the indices
    indices = torch.randperm(X.size(0))

    # Calculate the number of test samples
    test_count = int(test_size * X.size(0))

    # Split the indices for train and test
    test_indices = indices[:test_count]
    train_indices = indices[test_count:]

    # Create train and test sets
    X_train, y_train = X[train_indices], y[train_indices]
    X_test, y_test = X[test_indices], y[test_indices]

    return X_train, X_test, y_train, y_test

def get_batches(X, y, batch_size):
    n_samples = X.shape[0]
    indices = np.arange(n_samples)
    np.random.shuffle(indices)

    for start in range(0, n_samples, batch_size):
        end = min(start + batch_size, n_samples)
        
        batch_idx = indices[start:end]
        
        yield X[batch_idx, :], y[batch_idx]

class LassoRegression(nn.Module):
    def __init__(self, n_features, l1_penalty):
        super(LassoRegression, self).__init__()
        self.linear = nn.Linear(n_features, 1,bias=False)
        self.l1_penalty = l1_penalty

    def forward(self, x):
        return self.linear(x).squeeze()

    def lasso_loss(self, y_pred, y):
        return nn.MSELoss()(y_pred, y) + self.l1_penalty * torch.norm(self.linear.weight, 1)
    
    def generate(self, x): # takes normal list and returns model prediction
        return self(torch.tensor(x,dtype=torch.float)).item()
    
    def print_weights(self):
        for name, param in self.named_parameters():
            if param.requires_grad:
                print(name, param.data)     

def train(model, X_train, y_train, X_val, y_val, epochs, batch_size, learning_rate):
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    train_losses = []
    val_losses = []

    for epoch in range(epochs):
        # Training
        model.train()
        batch_trainlosses = []
        for X_batch, y_batch in get_batches(X_train, y_train, batch_size):
            y_pred = model(X_batch)
            loss = model.lasso_loss(y_pred, y_batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            batch_trainlosses.append(loss.item())
        train_losses.append(np.mean(batch_trainlosses))

        # Validation
        model.eval()
        batch_vallosses = []
        with torch.no_grad():
            for X_valbatch, y_valbatch in get_batches(X_val, y_val, batch_size):
                y_pred = model(X_valbatch)
                loss = model.lasso_loss(y_pred, y_valbatch)
                batch_vallosses.append(loss.item())
            val_losses.append(np.mean(batch_vallosses))

        print(f'Epoch {epoch+1}/{epochs} => Train Loss: {train_losses[-1]}, Val Loss: {val_losses[-1]}')

    return train_losses, val_losses

def main():
    
    kfold = KFold(n_splits=k, shuffle=True)
    
    for fold, (train_ids, val_ids) in enumerate(kfold.split(dataset)):
        # Split data
        X_train, X_val, y_train, y_val = dataset[train_ids,:-1], dataset[val_ids,:-1], dataset[train_ids,-1], dataset[val_ids,-1]
        
        # Load model
        model = LassoRegression(n_SNPs, l1_penalty=l1_penalties[fold])
        model_file = directory + f'model_{fold}.pth'
        if os.path.isfile(model_file) and input("load model: y/n") == 'y':
            model.load_state_dict(torch.load(model_file))

        # Train model
        train_losses, val_losses = train(model, X_train, y_train, X_val, y_val, epochs=epochs, batch_size=batch_size, learning_rate=learning_rate)

        # Save model
        torch.save(model.state_dict(), model_file)

        # Save losses and pred|actual pairs to csv
        vd.save_losses_to_csv(train_losses, val_losses, directory + f'losses_{fold}.csv')
        vd.save_correlation_to_csv(model(X_val), y_val, directory + f'correlation_{fold}.csv')

        # Print model weights
        model.print_weights()
        
    
if __name__ == '__main__':
    main()


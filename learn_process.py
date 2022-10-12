from data.dataset import DatasetSimulationData
from data.dataloader import DataLoader
from data.transforms import NormalizeTransform, ComposeTransform, ReduceTo2DTransform, PowerOfTwoTransform, ToTensorTransform
from networks.unet_leiterrl import weights_init
from tqdm.auto import tqdm
import logging

from torch.optim import Adam, lr_scheduler
from torch.utils.tensorboard import SummaryWriter
import torch.nn as nn
import torch.nn.functional as F

def test_dummy():
    # dummy test
    #TODO ask Ishaan
    assert 1 == 1

# create and directly split dataset into train, val, test
def init_data(reduce_to_2D = True, reduce_to_2D_wrong = False, overfit = False, normalize=True, just_plotting=False, batch_size=100, inputs="all",
            dataset_name="approach2_dataset_generation_simplified/dataset_HDF5_testtest", path_to_datasets="/home/pelzerja/Development/simulation_groundtruth_pflotran/Phd_simulation_groundtruth"):
    """
    Initialize dataset and dataloader for training.

    Parameters
    ----------
    reduce_to_2D : bool
        If true, reduce the dataset to 2D instead of 3D
    overfit : bool
        If true, only use a small subset of the dataset for training, achieved by cheating: changing the split ratio
    normalize : bool
        If true, normalize the dataset, usually the case; not true for testing input data magnitudes etc 
    dataset_name : str
        Name of the dataset to use (has to be the same as in the folder)
    batch_size : int
        Size of the batch to use for training
    
    Returns
    -------
    datasets : dict
        Dictionary of datasets, with keys "train", "val", "test"
    dataloaders : dict
        Dictionary of dataloaders, with keys "train", "val", "test"
    """
    
    datasets = {}
    transforms_list = [ToTensorTransform(), PowerOfTwoTransform(oriented="left")]
    if reduce_to_2D:
        transforms_list.append(ReduceTo2DTransform(reduce_to_2D_wrong=reduce_to_2D_wrong))
    if normalize:
        transforms_list.append(NormalizeTransform(reduced_to_2D=reduce_to_2D))
    logging.info(f"transforms_list: {transforms_list}")


    transforms = ComposeTransform(transforms_list)
    split = {'train': 0.6, 'val': 0.2, 'test': 0.2} if not overfit else {'train': 1, 'val': 0, 'test': 0}
    
    # just plotting (for Marius)
    if just_plotting:
        split = {'train': 1, 'val': 0, 'test': 0}
        transforms = None

    input_list = [inputs[i] for i in range(len(inputs))]
    input_vars = []
    if 'x' in input_list:
        input_vars.append("Liquid X-Velocity [m_per_y]")
    if 'y' in input_list:
        input_vars.append("Liquid Y-Velocity [m_per_y]")
    if 'z' in input_list:
        input_vars.append("Liquid Z-Velocity [m_per_y]")
    if 'p' in input_list:
        input_vars.append("Liquid_Pressure [Pa]")
    if 't' in input_list:
        input_vars.append("Temperature [C]")
    #if '-' not in input_list:
    input_vars.append("Material_ID")

    for mode in ['train', 'val', 'test']:
        temp_dataset = DatasetSimulationData(
            dataset_name=dataset_name, dataset_path=path_to_datasets, 
            transform=transforms, input_vars=input_vars,
            output_vars=["Temperature [C]"], #. "Liquid_Pressure [Pa]"
            mode=mode, split=split
        )
        datasets[mode] = temp_dataset

    # Create a dataloader for each split.
    dataloaders = {}
    for mode in ['train', 'val', 'test']:
        temp_dataloader = DataLoader(
            dataset=datasets[mode],
            batch_size=batch_size,
            shuffle=True,
            drop_last=False,
        )
        dataloaders[mode] = temp_dataloader

    # # Assert if data is not 2D
    # def assertion_error_2d(datasets):
    #     for dataset in datasets["train"]:
    #         shape_data = len(dataset['x'].shape)
    #         break
    #     assert shape_data == 3, "Data is not 2D"
    # 
    # assertion_error_2d(datasets)

    return datasets, dataloaders

def train_model(model, dataloaders, loss_fn, n_epochs, lr, name_folder, debugging=False):
    """
    Train the model for a certain number of epochs.
        
    Parameters
    ----------
    model : torch.nn.Module
        Choose the model to train with varying structure etc
    dataloaders : dict
        Dictionary of dataloaders, with keys "train", "val", "test"
    loss_fn : torch.nn.Module
        Loss function to use, e.g. MSELoss() - depends on the model
    n_epochs : int
        Number of epochs to train for
    lr : float
        Learning rate to use

    Returns
    -------
        model : torch.nn.Module
            Trained model, ready to be applied to data;
            returns data in format of (Batch_id, channel_id, H, W)
    """

    # initialize Adam optimizer
    optimizer = Adam(model.parameters(), lr=lr) 
    # initialize tensorboard
    if not debugging:
        writer = SummaryWriter(f"runs/{name_folder}")
    loss_hist = []
    scheduler = lr_scheduler.ReduceLROnPlateau(optimizer)

    model.apply(weights_init)
    epochs = tqdm(range(n_epochs), desc = "epochs")
    for epoch in epochs:
        for batch_idx, data_point in enumerate(dataloaders["train"]):
            # datasets["train"] contains 3 data points
            x = data_point["x"].float()
            y = data_point["y"].float()

            model.zero_grad()
            optimizer.zero_grad()

            y_out = model(x) # dimensions: (batch-datapoint_id, channel, x, y)
            mse_loss = loss_fn(y_out, y)
            loss = mse_loss
            
            loss.backward()
            optimizer.step()
            epochs.set_postfix_str(f"loss: {loss.item():.4f}")

            loss_hist.append(loss.item())
            scheduler.step(loss)
            
            if not debugging:
                writer.add_scalar("loss", loss.item(), epoch*len(dataloaders["train"])+batch_idx)
                writer.add_image("y_out_0", y_out[0,0,:,:], dataformats="WH", global_step=epoch*len(dataloaders["train"])+batch_idx)
                #writer.add_image("y_out_1", y_out[0,1,:,:], dataformats="WH")

        if not debugging:
            writer.add_image("x_0", x[0,0,:,:], dataformats="WH")
            # writer.add_image("x_1", x[0,1,:,:], dataformats="WH")
            # writer.add_image("x_2", x[0,2,:,:], dataformats="WH")
            # writer.add_image("x_3", x[0,3,:,:], dataformats="WH")
            # writer.add_image("x_4", x[0,4,:,:], dataformats="WH")
            # writer.add_image("y_0", y[0,0,:,:], dataformats="WH")
            # #writer.add_image("y_1", y[0,1,:,:], dataformats="WH")


    # if not debugging:
    #     writer.add_graph(model, x)
    print('Finished Training')

    return loss_hist

if __name__ == "__main__":
    init_data()
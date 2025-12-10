import torch

# Affichera le numéro de version CUDA, et non plus None
print(f"Version CUDA de PyTorch : {torch.version.cuda}")

# Teste si PyTorch détecte votre GPU
print(f"GPU disponible : {torch.cuda.is_available()}")

# Affiche le nom de votre GPU
if torch.cuda.is_available():
    print(f"Nom du GPU : {torch.cuda.get_device_name(0)}")
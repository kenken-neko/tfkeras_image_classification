import argparse
import os
import tensorflow_datasets as tfds
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, TensorBoard

from models import SimpleCNNModel, VGG16Model, XceptionModel
from original_dataset_loader import OriginalDatasetLoader
from preprocess import TFImagePreprocessing


def main(
    dataset_name,
    original_dataset_path,
    dataset_size,
    augmentation_times,
    augmentation_seed,
    valid_per_train,
    model_type,
    is_fine_tuning,
    is_dropout,
    epochs,
    batch_size,
    optimizer,
):
    # Set paths
    exe_dir = os.path.dirname(os.path.abspath(__file__))
    output_model_dir = os.path.join(exe_dir, ".." ,"models")
    log_dir = os.path.join(exe_dir, ".." , "tmp_logs")

    # Load train dataset
    train_ratio = int((1 - valid_per_train) * 100)
    if dataset_name:
        # Load existing dataset from Tensorflow_datasets
        (train_dataset, valid_dataset), info = tfds.load(
            name=dataset_name,
            split=[
                f"train[:{train_ratio}%]",  # Train dataset
                f"train[{train_ratio}%:]",  # Valid dataset
            ],
            with_info=True,
        )
        hight_size, width_size, channel_size = info.features["image"].shape
        num_classes = info.features["label"].num_classes
    elif original_dataset_path:
        # Load original dataset from directory
        ds_loader = OriginalDatasetLoader(
            original_dataset_path,
            valid_per_train,
            output_label_dict_path=os.path.join(
                output_model_dir, f"{model_type}_label_dict.csv"
            ),
        )
        (train_dataset, valid_dataset), info = ds_loader.load()
        hight_size = info["hight_size"]
        width_size = info["width_size"]
        channel_size = info["channel_size"]
        num_classes = info["num_classes"]
    else:
        raise AssertionError("The dataset is not specified correctly.")

    # Train dataset size
    if dataset_size != -1:
        train_dataset = train_dataset.shuffle(len(train_dataset)).take(dataset_size)

    # Image preprocess instance
    img_prep = TFImagePreprocessing(
        hight_size=hight_size,
        width_size=width_size,
        channel_size=channel_size,
        num_classes=num_classes,
    )

    # Preprocess datasets and prepare model
    if model_type == "SimpleCNN":
        # Image resizes
        train_dataset = train_dataset.map(img_prep.base_preprocess)
        valid_dataset = valid_dataset.map(img_prep.base_preprocess)
        # Prepare model
        model = SimpleCNNModel(
            hight_size=hight_size,
            width_size=width_size,
            channel_size=channel_size,
            num_classes=num_classes,
            is_dropout=is_dropout,
        )
    elif model_type == "VGG16":
        # Image resizes
        train_dataset = train_dataset.map(img_prep.vgg_preprocess)
        valid_dataset = valid_dataset.map(img_prep.vgg_preprocess)
        # Prepare model
        model = VGG16Model(
            num_classes=num_classes,
            is_fine_tuning=is_fine_tuning,
            is_dropout=is_dropout,
        )
    elif model_type == "Xception":
        # Image resizes
        train_dataset = train_dataset.map(img_prep.xception_preprocess)
        valid_dataset = valid_dataset.map(img_prep.xception_preprocess)
        # Prepare model
        model = XceptionModel(
            num_classes=num_classes,
            is_fine_tuning=is_fine_tuning,
            is_dropout=is_dropout,
        )
    else:
        raise ValueError(f"The model: {model_type} does not exist.")

    # Image augmentation
    if augmentation_times:
        train_dataset = train_dataset.repeat(augmentation_times).map(
            lambda x, y: (img_prep.rand_augment(x, augmentation_seed), y)
        )
    # Batch
    train_dataset = train_dataset.batch(batch_size)
    valid_dataset = valid_dataset.batch(batch_size)

    # Build models
    model = model.build()
    model.compile(
        optimizer=optimizer,
        loss="categorical_crossentropy",
        metrics=["acc"],
    )

    model_file_name = model_type + ".h5"
    output_model_path = os.path.join(output_model_dir, model_file_name)
    # Preparing callbacks
    callbacks = [
        TensorBoard(log_dir=log_dir),
        EarlyStopping(patience=3),
        ModelCheckpoint(output_model_path),
    ]

    # Train the model
    history = model.fit(
        train_dataset,
        batch_size=batch_size,
        epochs=epochs,
        callbacks=callbacks,
        validation_data=valid_dataset,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parameters for train task")
    parser.add_argument(
        "--dataset_name", type=str, default=None
    )  # Ex.: mnist, fashion_mnist, cifar10
    parser.add_argument("--original_dataset_path", type=str, default=None)
    parser.add_argument("--dataset_size", type=int, default=-1)
    parser.add_argument("--augmentation_times", type=int, default=0)
    parser.add_argument("--augmentation_seed", type=int, default=0)
    parser.add_argument("--valid_per_train", type=float, default=0.2)
    parser.add_argument("--model_type", type=str, default="SimpleCNN")
    parser.add_argument("--is_fine_tuning", action="store_true")
    parser.add_argument("--is_dropout", action="store_true")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--optimizer", type=str, default="adam")
    args = parser.parse_args()
    main(
        dataset_name=args.dataset_name,
        original_dataset_path=args.original_dataset_path,
        dataset_size=args.dataset_size,
        augmentation_times=args.augmentation_times,
        augmentation_seed=args.augmentation_seed,
        valid_per_train=args.valid_per_train,
        model_type=args.model_type,
        is_fine_tuning=args.is_fine_tuning,
        is_dropout=args.is_dropout,
        epochs=args.epochs,
        batch_size=args.batch_size,
        optimizer=args.optimizer,
    )

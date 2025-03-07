import dagger
import asyncio
import argparse

async def setup_ros2_humble(install_moveit=True, install_control_nav=True, 
                           install_gpu_drivers=True, install_isaac_sim=True):
    """Sets up ROS 2 Humble with optional components.
    
    Args:
        install_moveit (bool): Whether to install MoveIt 2
        install_control_nav (bool): Whether to install ROS 2 Control and Navigation
        install_gpu_drivers (bool): Whether to install NVIDIA GPU drivers
        install_isaac_sim (bool): Whether to install Isaac Sim 4.2
    """
    async with dagger.Connection() as client:
        # Start with Ubuntu 22.04 with NVIDIA CUDA (required for Isaac Sim)
        ubuntu = client.container().from_("nvidia/cuda:12.1.1-devel-ubuntu22.04")

        # Install ROS 2 Humble and dependencies (base layer - always installed)
        container = (
            ubuntu.with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "software-properties-common", "gnupg", "curl"])
            # Add ROS 2 repository and GPG key
            .with_exec([
                "sh", "-c", 
                "curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | " +
                "gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg"
            ])
            .with_exec([
                "sh", "-c",
                "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main' > /etc/apt/sources.list.d/ros2.list"
            ])
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "ros-humble-desktop"])
            # Install essential ROS tools
            .with_exec(["apt-get", "install", "-y", "python3-rosdep", "python3-colcon-common-extensions"])
            # Initialize rosdep
            .with_exec(["rosdep", "init"])
            .with_exec(["rosdep", "update"])
        )

        print("Installing ROS 2 Humble")

        # Install MoveIt 2 for motion planning if requested
        if install_moveit:
            container = container.with_exec(["apt-get", "install", "-y", "ros-humble-moveit"])
            print("Including MoveIt 2 installation")

        # Install ROS 2 Control and Navigation Stack if requested
        if install_control_nav:
            container = (
                container
                .with_exec(["apt-get", "install", "-y", "ros-humble-ros2-control"])
                .with_exec(["apt-get", "install", "-y", "ros-humble-navigation2"])
                .with_exec(["apt-get", "install", "-y", "ros-humble-nav2-bringup"])
            )
            print("Including ROS 2 Control and Navigation installation")

        # Install NVIDIA drivers for GPU support if requested
        if install_gpu_drivers:
            container = (
                container
                .with_exec(["apt-get", "install", "-y", "nvidia-driver-525"])
                .with_exec(["apt-get", "install", "-y", "nvidia-container-toolkit"])
            )
            print("Including NVIDIA GPU drivers installation")

        # Install Isaac Sim 4.2 if requested
        if install_isaac_sim:
            container = (
                container
                .with_exec([
                    "wget", "https://developer.nvidia.com/downloads/omniverse-isaac-sim-422-linux"
                ])
                .with_exec(["chmod", "+x", "omniverse-isaac-sim-422-linux"])
                .with_exec(["./omniverse-isaac-sim-422-linux", "--silent"])
            )
            print("Including Isaac Sim 4.2 installation")

        # Set up environment variables
        container = (
            container
            .with_env_variable("ROS_DISTRO", "humble")
            .with_env_variable("ROS_PACKAGE_PATH", "/opt/ros/humble/share")
            .with_env_variable("PATH", "/opt/ros/humble/bin:$PATH")
            .with_env_variable("LD_LIBRARY_PATH", "/opt/ros/humble/lib:$LD_LIBRARY_PATH")
            .with_env_variable("AMENT_PREFIX_PATH", "/opt/ros/humble:$AMENT_PREFIX_PATH")
        )

        # Add GPU-specific environment variables if GPU drivers are installed
        if install_gpu_drivers:
            container = (
                container
                .with_env_variable("NVIDIA_VISIBLE_DEVICES", "all")
                .with_env_variable("NVIDIA_DRIVER_CAPABILITIES", "all")
            )

        # Add Isaac Sim environment variable if installed
        if install_isaac_sim:
            container = container.with_env_variable("ISAACSIM_PATH", "/opt/NVIDIA/Omniverse/Isaac-Sim-4.2")

        # Verify installation
        verification_commands = ["ros2", "pkg", "list"]  # Base ROS 2 verification
        
        # Add verification commands for optional components
        test_container = container.with_exec(verification_commands)
        
        if install_moveit:
            test_container = test_container.with_exec(
                ["ros2", "launch", "moveit_resources_panda_moveit_config", "demo.launch.py"])
        
        if install_isaac_sim and install_gpu_drivers:
            test_container = test_container.with_exec(["ls", "$ISAACSIM_PATH"])

        # Execute the container and return the result
        return await test_container.exit_code()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up ROS 2 Humble with optional components"
    )
    parser.add_argument("--none", action="store_true",
                        help="Disable all optional components (MoveIt, Control/Navigation, GPU drivers, Isaac Sim)")
    parser.add_argument("--no-moveit", action="store_false", dest="install_moveit",
                        help="Skip MoveIt 2 installation")
    parser.add_argument("--no-control-nav", action="store_false", dest="install_control_nav",
                        help="Skip ROS 2 Control and Navigation installation")
    parser.add_argument("--no-gpu", action="store_false", dest="install_gpu_drivers",
                        help="Skip NVIDIA GPU drivers installation")
    parser.add_argument("--no-isaac", action="store_false", dest="install_isaac_sim",
                        help="Skip Isaac Sim 4.2 installation")
    
    args = parser.parse_args()
    
    # If --none is specified, disable all optional components
    if args.none:
        args.install_moveit = False
        args.install_control_nav = False
        args.install_gpu_drivers = False
        args.install_isaac_sim = False
    else:
        # Set defaults only if --none is not specified
        parser.set_defaults(
            install_moveit=True,
            install_control_nav=True,
            install_gpu_drivers=True,
            install_isaac_sim=True
        )
    
    return args

# Run the pipeline
if __name__ == "__main__":
    args = parse_arguments()
    print(f"Setting up ROS 2 Humble with the following components:")
    print(f"- MoveIt 2: {'Yes' if args.install_moveit else 'No'}")
    print(f"- ROS 2 Control and Navigation: {'Yes' if args.install_control_nav else 'No'}")
    print(f"- NVIDIA GPU drivers: {'Yes' if args.install_gpu_drivers else 'No'}")
    print(f"- Isaac Sim 4.2: {'Yes' if args.install_isaac_sim else 'No'}")
    
    asyncio.run(setup_ros2_humble(
        install_moveit=args.install_moveit,
        install_control_nav=args.install_control_nav,
        install_gpu_drivers=args.install_gpu_drivers,
        install_isaac_sim=args.install_isaac_sim
    ))

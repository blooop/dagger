#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.10"
# dependencies = [
#   "dagger-io",
# ]
# ///

import sys
import dagger
import asyncio
import subprocess
import os
import tempfile
import time

async def setup_ros2_humble(client):
    # Create container
    container = client.container()
    
    # Base setup
    container = (
        container.from_("osrf/ros:humble-desktop")
        # Set environment variables
        .with_env_variable("DEBIAN_FRONTEND", "noninteractive")
        .with_env_variable("ROS_DISTRO", "humble")
        .with_env_variable("TERM", "xterm-256color")
        .with_env_variable("COLORTERM", "truecolor")
        # Create non-root user
        .with_exec(["groupadd", "-g", "1000", "ros"])
        .with_exec(["useradd", "-m", "-u", "1000", "-g", "ros", "ros"])
        .with_exec(["usermod", "-aG", "sudo", "ros"])
        # Install basic dependencies
        .with_exec(["apt-get", "update"])
        .with_exec([
            "apt-get", "install", "-y",
            "python3-pip",
            "python3-colcon-common-extensions",
            "python3-vcstool",
            "git",
            "sudo",
            "ros-humble-moveit",
            "ros-humble-moveit-resources-panda-moveit-config",
            "ros-humble-controller-manager",
            "ros-humble-joint-state-publisher",
            "ros-humble-joint-state-publisher-gui",
            "ros-humble-robot-state-publisher",
            "ros-humble-xacro",
            "ros-humble-rviz2",
            "ros-humble-joint-state-broadcaster",
            "ros-humble-position-controllers",
            "ros-humble-joint-trajectory-controller",
            "ros-humble-gripper-controllers",
            "ros-humble-ros2-control",
            "ros-humble-ros2-control-test-assets",
            "ros-humble-controller-manager-msgs",
            "ros-humble-hardware-interface",
            "ros-humble-control-msgs",
            "python3-numpy",
            "python3-transforms3d"
        ])
    )

    # Create workspace and clone dependencies
    container = (
        container
        .with_exec(["mkdir", "-p", "/home/ros/ws/src"])
        .with_new_file("/home/ros/ws/depends.repos", """repositories:
  pymoveit2:
    type: git
    url: https://github.com/AndrejOrsula/pymoveit2.git
    version: master
""")
        .with_exec(["chown", "-R", "ros:ros", "/home/ros/ws"])
        .with_user("ros")
        .with_workdir("/home/ros/ws")
        .with_exec(["/bin/bash", "-c", "vcs import src < depends.repos"])
        .with_exec(["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && rosdep update && rosdep install --from-paths src --ignore-src -r -y"])
        .with_exec(["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && colcon build"])
    )
    
    # Setup bashrc
    container = (
        container
        .with_new_file("/home/ros/.bashrc", """
source /opt/ros/humble/setup.bash
source /home/ros/ws/install/setup.bash

# Enable color support
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias dir='dir --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# Colored GCC warnings and errors
export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# Force color terminal
export TERM=xterm-256color
export COLORTERM=truecolor
""")
    )
    
    # Run the PyMoveIt2 example
    container.with_exec([
        "/bin/bash", "-c",
        "source /opt/ros/humble/setup.bash && source /home/ros/ws/install/setup.bash && python3 /home/ros/ws/src/pymoveit2/examples/ex_joint_goal.py --ros-args -p joint_positions:=[0.0,0.7,0.0,-0.7,0.0,0.7,0.0]"
    ])
    
    return container

def start_container():
    # Common docker arguments
    docker_args = [
        "--network=host",
        "--privileged",
        "--rm",
        "-it",
        "-e ROS_DOMAIN_ID=42",
        "-e PYTHONUNBUFFERED=1",  # Ensure Python output is not buffered
        "-e DISPLAY=:1",  # Use VNC display
        "-e QT_QPA_PLATFORM=offscreen",  # Use offscreen platform
        "--user=ros"  # Run as ros user
    ]

    # Launch MoveIt demo with RViz and run PyMoveIt2 example
    cmd = [
        "docker", "run",
        *docker_args,
        "ros2-humble:latest",
        "/bin/bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "source /home/ros/ws/install/setup.bash && "
        "(ros2 launch moveit_resources_panda_moveit_config demo.launch.py rviz:=false & "  # Disable RViz for now
        "echo 'Waiting for MoveIt to initialize...' && "
        "sleep 15 && "  # Give more time for MoveIt to initialize
        "ros2 run joint_state_publisher joint_state_publisher --ros-args -p source_list:=['/joint_states'] -p joint_names:=['panda_joint1','panda_joint2','panda_joint3','panda_joint4','panda_joint5','panda_joint6','panda_joint7'] -p publish_default_positions:=true -p publish_default_velocities:=true -p publish_default_efforts:=true & "  # Start joint state publisher with Panda joints
        "echo 'Waiting for joint state publisher to initialize...' && "
        "sleep 5 && "  # Give time for joint state publisher to initialize
        "cd /home/ros/ws/src/pymoveit2/examples && "
        "echo 'Running PyMoveIt2 example...' && "
        "python3 ex_joint_goal.py --ros-args -p use_sim_time:=false -p joint_positions:=[0.0,0.0,0.0,0.0,0.0,0.0,0.0]) || "  # Set all joints to zero
        "echo 'Error occurred' && exit 1"
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running container: {e}")
        raise
    except KeyboardInterrupt:
        print("\nStopping container...")
        subprocess.run(["docker", "ps", "-q", "-l"], capture_output=True, text=True, check=True)

async def main():
    print("Starting Dagger pipeline for ROS 2 Humble setup with MoveIt...")
    
    async with dagger.Connection(dagger.Config(log_output=sys.stderr)) as client:
        # Build the container with Dagger
        container = await setup_ros2_humble(client)
        
        # Export the container to a temporary file
        print("\nExporting container...")
        with tempfile.NamedTemporaryFile() as tmp:
            await container.export(tmp.name)
            
            # Load the container into Docker
            print("Loading container into Docker...")
            subprocess.run(["docker", "load"], stdin=open(tmp.name, "rb"), check=True)
            
            # Get the image ID and tag it
            result = subprocess.run(
                ["docker", "images", "--format", "{{.ID}}", "--no-trunc"],
                capture_output=True,
                text=True,
                check=True
            )
            image_id = result.stdout.strip().split('\n')[0]
            subprocess.run(["docker", "tag", image_id, "ros2-humble:latest"], check=True)
        
        print("\nContainer ready!")
        
        # Start the container
        start_container()

if __name__ == "__main__":
    asyncio.run(main()) 
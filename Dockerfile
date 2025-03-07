FROM osrf/ros:humble-desktop

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV TERM=xterm-256color
ENV COLORTERM=truecolor

# Create non-root user
RUN groupadd -g 1000 ros && \
    useradd -m -u 1000 -g ros ros && \
    usermod -aG sudo ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ros && \
    chmod 0440 /etc/sudoers.d/ros

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    git \
    sudo \
    ros-humble-moveit \
    ros-humble-moveit-resources-panda-moveit-config && \
    pip3 install pymoveit2

# Create workspace
RUN mkdir -p /home/ros/ws/src/moveit_demo/scripts /home/ros/ws/src/moveit_demo/moveit_demo

# Copy package files
COPY package.xml /home/ros/ws/src/moveit_demo/
COPY CMakeLists.txt /home/ros/ws/src/moveit_demo/
COPY moveit_demo.py /home/ros/ws/src/moveit_demo/scripts/
COPY __init__.py /home/ros/ws/src/moveit_demo/moveit_demo/

# Set permissions
RUN chown -R ros:ros /home/ros

# Switch to ros user
USER ros
WORKDIR /home/ros/ws

# Build workspace
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    colcon build"

# Source workspace in bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> /home/ros/.bashrc && \
    echo "source /home/ros/ws/install/setup.bash" >> /home/ros/.bashrc

CMD ["bash"] 
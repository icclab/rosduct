FROM ros:noetic-ros-base

# fix failing apt conf (TODO: remove when no longer an issue)
RUN rm /etc/apt/apt.conf.d/docker-clean 

ENV user=ros
ENV workspace=/home/ros
ENV ROS_DISTRO=noetic

# add ros user to container and make sudoer
RUN useradd -m -s /bin/bash -G video,plugdev  ${user} && \
echo "${user} ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/${user}" && \
chmod 0440 "/etc/sudoers.d/${user}"

# add user to video group
RUN adduser ${user} video
RUN adduser ${user} plugdev

# Switch to user
USER "${user}"
# Switch to the workspace
WORKDIR ${workspace}
# edit bashrc
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc

RUN sudo apt update && sudo apt install -y git python3-catkin-tools python3-pip 
RUN /bin/bash -c "source /opt/ros/${ROS_DISTRO}/setup.bash && \
    rosdep update && \
    mkdir -p catkin_ws && \ 
    cd catkin_ws && \
    catkin_init_workspace"

COPY . /home/${user}/catkin_ws/src/rosduct
RUN sudo chown -R ${user}:${user} catkin_ws
RUN /bin/bash -c "source /opt/ros/${ROS_DISTRO}/setup.bash && \
    cd catkin_ws && \
    rosdep install -r --from-paths . --ignore-src --rosdistro $ROS_DISTRO -y && \
    pip3 install -r src/rosduct/requirements.txt && \
    catkin build"

CMD ["/bin/bash", "-c", "source ~/catkin_ws/devel/setup.bash ; roslaunch rosduct client_summit_xl.launch"]
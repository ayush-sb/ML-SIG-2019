#!/usr/bin/env python
import numpy as np
import sys
import csv
import matplotlib.pyplot as plt
from pprint import pprint

# utility to read csv track files into numpy arrays
def read_track(in_file="tracks/sample_path.csv", scale=[1000, 600]):
    x = []
    y1 = []
    y2 = []
    with open(in_file, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            x.append(float(row[0]))
            y1.append(float(row[1]))
            y2.append(float(row[2]))
    return scale[0] * np.array(x), scale[1] * np.array(y1), scale[1] * np.array(y2)


def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


class Car:
    def __init__(self, track, accl_function):
        self.accl_function = accl_function
        self.eyes = np.array([[0, 1], [0, -1], [1, 1], [1, -1]])
        self.track = track
        self.track_at = lambda x: (
            np.interp(x, self.track[0], self.track[1]),
            np.interp(x, self.track[0], self.track[2]),
        )
        self.pos = np.array(
            (
                track[0][0] + 1,
                np.random.uniform(
                    (track[1][0] + track[2][0]) / 4, 3 * (track[1][0] + track[2][0]) / 4
                ),
            )
        )
        # self.pos = np.array((track[0][0], track[1][0]+10))
        self.max_dist = 1000
        self.accl = np.zeros((2,))
        self.vel = np.zeros((2,))
        self.last_vel = np.zeros((2,))
        self.max_vel = np.array([25, 25])
        self.last_pos = np.zeros((2,))
        self.pos_history = [np.copy(self.pos)]
        self.vel_history = [np.copy(self.vel)]
        self.accl_history = [np.copy(self.accl)]
        self.end = self.track[0][-1]

    def is_legal(self):
        t = self.track_at(self.pos[0])
        return (t[0] < self.pos[1] < t[1]) and (0 < self.pos[0] < self.end)

    def get_rot_mat(self, th):
        return np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])

    def default_accl_function(params, **kwargs):
        distances = params[:4]
        du, dd, _, _ = distances
        last_dist = params[4:8]
        last_vel = params[8:10]
        accl = [0, 0]
        accl[0] = 0.1  # Accel along x axis

        # Accel along y axis which takes into account the distances from the tracks
        accl[1] = (1 + du) / (1 + dd) - 1

        if distances[0] < 200 or distances[2] < 200:
            accl[1] -= 0.2

        if distances[1] < 200 or distances[3] < 200:
            accl[1] += 0.2

        return np.array(accl)

    def run(self, **kwargs):
        dist = self.get_surrounding(self.pos, self.vel)
        last_dist = self.get_surrounding(self.last_pos, self.last_vel)
        params = np.array([*dist, *self.vel, *last_dist, *self.last_vel])
        self.accl = self.accl_function(params, **kwargs)
        self.update()
        return params

    def update(self):
        self.last_pos = np.copy(self.pos)
        self.last_vel = np.copy(self.vel)

        if self.vel[0] > self.max_vel[0]:
            self.vel[0] = self.max_vel[0]
        if self.vel[0] < 0:
            self.vel[0] = 0
        if self.vel[1] > self.max_vel[1]:
            self.vel[1] = self.max_vel[1]
        if self.vel[1] < -self.max_vel[1]:
            self.vel[1] = -self.max_vel[1]
        self.pos += self.vel
        if self.is_legal():
            self.vel += self.accl
        else:
            self.pos = self.last_pos
            self.vel = np.zeros((2,))
            self.accl = np.zeros((2,))

        self.pos_history.append(np.copy(self.pos))
        self.vel_history.append(np.copy(self.vel))
        self.accl_history.append(np.copy(self.accl))
        # plt.scatter(self.get_surrounding(),50,color='y')

    def plot_history(self):
        plt.plot(self.track[0], self.track[1], c="k")
        plt.plot(self.track[0], self.track[2], c="k")
        plt.plot(*zip(*self.pos_history))
        plt.gca().set_xlim(-10, 1010)
        plt.gca().set_ylim(-10, 610)

    def utility(self):
        """
        Utility(): returns the utility of the car
        Returns: max_dist,time
            max_dist: maximum distance travelled by the car
            time: time taken to finish the track (-1 if car did not reach the end)
        """
        x_pos = np.array(self.pos_history)[:, 0]
        max_dist = np.max(x_pos)
        time = np.argmax(x_pos) if max_dist >= self.end - 2 else -1
        return max_dist, time

    def get_surrounding(self, pos, vel):
        if np.linalg.norm(vel) != 0:
            v1 = normalize(vel)
            rot_matrix = np.array([v1, [-v1[1], v1[0]]]).T
        else:
            rot_matrix = np.eye(2)
        # 2 is the num of dimensions
        rotated_eyes = self.eyes.dot(rot_matrix.T)

        xvals = np.arange(self.track[0].shape[0])
        vision_tensor = rotated_eyes * xvals[:, np.newaxis, np.newaxis]
        vision_tensor += np.expand_dims(pos, 1).T

        dists = np.zeros(self.eyes.shape[0])
        for i in range(self.eyes.shape[0]):
            # take upper track if line of vision is above 0
            if self.eyes[i][1] > 0:
                # find point on vision_tensor closest to track
                idx = np.argwhere(
                    np.diff(np.sign(vision_tensor[:, i, 1] - self.track[2]))
                ).flatten()
                # plt.scatter(*vision_tensor[idx,i].reshape(2,))

            # else take lower track
            else:
                # find point on vision_tensor closest to track
                idx = np.argwhere(
                    np.diff(np.sign(vision_tensor[:, i, 1] - self.track[1]))
                ).flatten()
                # plt.scatter(*vision_tensor[idx,i].reshape(2,))

            try:
                dists[i] = np.sqrt(
                    np.sum(np.square(vision_tensor[idx, i].reshape(2) - pos.reshape(2)))
                )
            except ValueError:
                dists[i] = self.max_dist
        return dists

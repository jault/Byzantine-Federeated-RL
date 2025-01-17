import numpy as np
from typing import Tuple
from gym.envs.registration import register

from highway_env import utils
from highway_env.envs.common.abstract import AbstractEnv
from highway_env.envs.common.action import Action
from highway_env.road.road import Road, RoadNetwork
from highway_env.vehicle.controller import ControlledVehicle


class HighwayEnv(AbstractEnv):
    """
    A highway driving environment.

    The vehicle is driving on a straight highway with several lanes, and is rewarded for reaching a high speed,
    staying on the rightmost lanes and avoiding collisions.
    """

    RIGHT_LANE_REWARD: float = 1.0#1.0#0.1
    """The reward received when driving on the right-most lanes, linearly mapped to zero for other lanes."""

    HIGH_SPEED_REWARD: float = 3.0#2.0#5.0#1.0 #0.4
    """The reward received when driving at full speed, linearly mapped to zero for lower speeds according to config["reward_speed_range"]."""

    LANE_CHANGE_REWARD: float = 0
    """The reward received at each lane change action."""

    def default_config(self) -> dict:
        config = super().default_config()
        config.update({
            "observation": {
                "type": "Kinematics",
                "vehicles_count": 5,# 10,
                "features": ["presence", "x", "y", "vx", "vy"],#,"cos_h", "sin_h"],
                "absolute": False,
                "order": "sorted",
            },
            "action": {
                "type": "DiscreteMetaAction",
            },
            "vehicles_count": 20,# 10,
            "lanes_count": 3,#4,
            "controlled_vehicles": 1,
            "initial_lane_id": None,
            "duration": 100,  # [s]
            "ego_spacing": 2,
            "vehicles_density": 1,
            "collision_reward": -5,#-2,#-5,#-1,  # The reward received when colliding with a vehicle.
            "reward_speed_range": [20, 30],
            "offroad_terminal": False,
            "policy_frequency": 1,
            "simulation_frequency": 10,
            "render_agent": False
        })
              
        # screen_width, screen_height = 84, 84
        # config.update({
        #     "offscreen_rendering": True,
        #     "observation": {
        #         "type": "GrayscaleObservation",
        #         "weights": [0.2989, 0.5870, 0.1140],  # weights for RGB conversion
        #         "stack_size": 4,
        #         "observation_shape": (screen_width, screen_height)
        #     },
        #     "vehicles_count": 10,# 10,
        #     "lanes_count": 4,#4,
        #     "controlled_vehicles": 1,
        #     "initial_lane_id": None,
        #     "screen_width": screen_width,
        #     "screen_height": screen_height,
        #     "scaling": 1.75,
        #     "policy_frequency": 1,
        #     "ego_spacing": 2,
        #     "duration": 100,
        #     "vehicles_density": 1,
        #     "reward_speed_range": [20, 30],
        #     "simulation_frequency": 10,
        #     "render_agent": False,
        #     "collision_reward": -5
        # })
                        
        return config

    def _reset(self) -> None:
        self._create_road()
        self._create_vehicles()

    def _create_road(self) -> None:
        """Create a road composed of straight adjacent lanes."""
        self.road = Road(network=RoadNetwork.straight_road_network(self.config["lanes_count"]),
                         np_random=self.np_random, record_history=self.config["show_trajectories"])

    def _create_vehicles(self) -> None:
        """Create some new random vehicles of a given type, and add them on the road."""
        self.controlled_vehicles = []
        for _ in range(self.config["controlled_vehicles"]):
            vehicle = self.action_type.vehicle_class.create_random(self.road,
                                                                   speed=25,
                                                                   lane_id=self.config["initial_lane_id"],
                                                                   spacing=self.config["ego_spacing"])
            self.controlled_vehicles.append(vehicle)
            self.road.vehicles.append(vehicle)

        vehicles_type = utils.class_from_path(self.config["other_vehicles_type"])
        for _ in range(self.config["vehicles_count"]):
            self.road.vehicles.append(vehicles_type.create_random(self.road, spacing=1 / self.config["vehicles_density"]))

    def _reward(self, action: Action) -> float:
        """
        The reward is defined to foster driving at high speed, on the rightmost lanes, and to avoid collisions.
        :param action: the last action performed
        :return: the corresponding reward
        """
        neighbours = self.road.network.all_side_lanes(self.vehicle.lane_index)
        lane = self.vehicle.target_lane_index[2] if isinstance(self.vehicle, ControlledVehicle) \
            else self.vehicle.lane_index[2]
        scaled_speed = utils.lmap(self.vehicle.speed, self.config["reward_speed_range"], [0, 1])
        reward = \
            + self.config["collision_reward"] * self.vehicle.crashed \
            + self.RIGHT_LANE_REWARD * lane / max(len(neighbours) - 1, 1) \
            + self.HIGH_SPEED_REWARD * np.clip(scaled_speed, 0, 1)
        # reward = utils.lmap(reward,
        #                   [self.config["collision_reward"], self.HIGH_SPEED_REWARD + self.RIGHT_LANE_REWARD],
        #                   [0, 1])
        reward = 0 if not self.vehicle.on_road else reward
        return reward

    def _is_terminal(self) -> bool:
        """The episode is over if the ego vehicle crashed or the time is out."""
        return self.vehicle.crashed or \
            self.steps >= self.config["duration"] or \
            (self.config["offroad_terminal"] and not self.vehicle.on_road)

    def _cost(self, action: int) -> float:
        """The cost signal is the occurrence of collision."""
        return float(self.vehicle.crashed)


register(
    id='highway-v0',
    entry_point='highway_env.envs:HighwayEnv',
)

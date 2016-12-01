import math
import random
import time

from model.ActionType import ActionType
from model.Faction import Faction
from model.Game import Game
from model.LaneType import LaneType
from model.MinionType import MinionType
from model.Move import Move
from model.SkillType import SkillType
from model.Wizard import Wizard
from model.World import World

debug = False
try:
    from debug_client import DebugClient
except:
    debug = None
else:
    debug = DebugClient()


class IndirectedGraph:

    def __init__(self):
        self.__adjacent = {}
        self.__vertex_count = 0
        self.__edges_count = 0

    def add_connection(self, source, destination):
        if source in self.__adjacent:
            self.__adjacent[source].append(destination)
        else:
            self.__adjacent[source] = [destination]

        if destination in self.__adjacent:
            self.__adjacent[destination].append(source)
        else:
            self.__adjacent[destination] = [source]

    def adjacent_nodes(self, source):
        return set(self.__adjacent[source])

    def vertex_degree(self, source):
        if source in self.__adjacent:
            return len(self.__adjacent[source])
        else:
            return None

    def vertexes(self):
        return self.__adjacent.keys()


class MyStrategy:
    # initials
    me = None
    world = None
    game = None
    move_ = None

    # constants section
    LOW_HP_FACTOR = [0.7, 0.72]
    ATTACK_RANGE = 700
    ALLY_RANGE = 600
    LOW_HP_ENEMY_SWITCH = 12 * 2                # 12 - wizard_damage
    PATH_FINDING_CELL_RADIUS = 35               # x2
    PATH_GRID_EXTEND = 200

    # TPR = 1  graph: 2.79, BFS: 0.3
    # TPR = 3  graph: 1.29, BFS: 0.1
    # TPR = 6  graph: 0.73, BFS: 0.05
    # TPR = 10 graph: 0.39, BFS: 0.05
    # TPR = 20
    TIME_PATH_RECALCULATE = 1
    TICK_OF_LAST_WAY = 0
    LAST_WAY = None

    # catch me
    MOVE_LOW_HP = 0
    MINION_STAY = [1360, 6]                     # check it
    ENEMIES_RANGE_LIMIT = [500, 490, 350, 200]  # wizard, building, fetish, orc TODO make it based on ATTACK RANGE value
    RANGE_LIMIT_ACTIVE = False

    # stuck defence
    NO_MOVE = 0
    PREVIOUS_POS = None
    MAX_NO_MOVE = 15
    FIGHTING = False

    # new waypoint system
    CURRENT_WAYPOINT_INDEX = 1
    LAST_WAYPOINT_INDEX = 0
    WAYPOINT_RADIUS_NEW = 85
    WAS_DEAD = True
    DEATH_COUNT = 0

    # bonus
    BONUS_POINT_TOP = [1200, 1200]
    BONUS_POINT_BOT = [2800, 2800]
    CREATE_BONUS_TICK = 2500
    BONUS_EXIST = False
    BONUS_COUNT = 0
    BONUS_GO = False

    # get modules initialised
    lane = LaneType()
    waypoints_top, waypoints_mid, waypoints_bot = [], [], []
    waypoints = []
    strategy_steps = 0
    start_positions = []
    respawn = []
    towers = []

    # optimization section
    graph_profile = 0
    bfs_profile = 0
    units_profile = 0
    init_profile = 0
    attack_profile = 0
    range_profiler = 0
    # graph profile
    gr_1 = 0
    gr_2 = 0
    gr_3 = 0
    gr_4 = 0
    gr_5 = 0
    new_gr = 0

    # debug parameters
    debug_next_milestone = [400, 3600]
    debug_next_waypoint = [400, 3600]
    debug_view_path = []
    debug_obstacles = []
    debug_distance_to_bonus = 10000
    debug_time_to_arrive = 0
    debug_attack_target = None
    debug_path_grid = None
    debug_obstacle_in_grid = None
    debug_message = None
    debug_graph_cells = 0
    debug_graph_cells_max = 0

    # game analisys parameters
    MIN_PUSH_AMOUNT = 2
    enemies_in_range = None
    wizard, building, fetish, orc = None, None, None, None
    ally_in_range = None
    my_target = None

    def visual_debugger(self):
        with debug.pre() as dbg:
            # road on top map
            dbg.line(100, 0, 100, 3500, (0, 0, 1))
            dbg.line(300, 800, 300, 3500, (0, 0, 1))
            dbg.line(300, 800, 800, 800, (0, 0, 1))
            dbg.line(100, 800, 100, 800, (0, 0, 1))
            dbg.line(100, 100, 3500, 100, (0, 0, 1))
            dbg.line(800, 300, 3500, 300, (0, 0, 1))
            dbg.line(800, 800, 800, 300, (0, 0, 1))

            for index in range(0, self.LAST_WAYPOINT_INDEX):
                dbg.circle(self.waypoints[index][0], self.waypoints[index][1], self.WAYPOINT_RADIUS_NEW, (0.5, 0.5, 0.5))
                dbg.text(self.waypoints[index][0], self.waypoints[index][1], '%s, x: %s, y: %s' %
                         (index, self.waypoints[index][0], self.waypoints[index][1]), (0.5, 0.5, 0.5))

            if self.debug_path_grid:
                dbg.rect(self.debug_path_grid[0], self.debug_path_grid[1], self.debug_path_grid[2],
                         self.debug_path_grid[3], (0, 0, 1))
                dbg.rect(self.debug_path_grid[0] + 10, self.debug_path_grid[1] + 10, self.debug_path_grid[2] - 10,
                         self.debug_path_grid[3] - 10, (0, 0, 1))

        with debug.post() as dbg:
            dbg.text(self.me.x - 45, self.me.y + 35, 'x: %s, y: %s' % (round(self.me.x), round(self.me.y)), (0, 0, 0))
            dbg.text(self.me.x - 45, self.me.y + 45, 'HP: %s, Mana %s' % (self.me.life, self.me.mana), (0, 0, 0))
            dbg.text(self.me.x - 45, self.me.y + 55, 'XP: %s, LVL %s' % (self.me.xp, self.me.level), (0, 0, 0))

            dbg.line(self.me.x, self.me.y, self.debug_next_milestone[0], self.debug_next_milestone[1], (0, 0, 0))
            dbg.line(self.me.x, self.me.y, self.debug_next_waypoint[0], self.debug_next_waypoint[1], (0, 0.5, 1))

            if len(self.debug_view_path) > 2:
                for i in range(2, len(self.debug_view_path)):
                    dbg.line(self.debug_view_path[i-1][0], self.debug_view_path[i-1][1],
                             self.debug_view_path[i][0], self.debug_view_path[i][1], (0.5, 0.5, 0.5))

            if len(self.debug_obstacles) > 0:
                for target in self.debug_obstacles:
                    dbg.circle(target.x, target.y, target.radius, (0, 0, 0))

            if self.debug_attack_target:
                dbg.fill_circle(self.debug_attack_target.x, self.debug_attack_target.y, self.debug_attack_target.radius, (1, 0, 0))

            if self.debug_message:
                dbg.text(self.me.x - 45, self.me.y + 65, self.debug_message, (0, 0, 0))

    def print_section(self):
        if self.strategy_steps % 100 == 0:
            print('My stats: hp %s of %s, score %s, coords: x %s y %s, level: %s xp: %s' %
                  (self.me.life, self.me.max_life, self.me.xp, round(self.me.x, 2),
                   round(self.me.y, 2), self.me.level, self.me.xp))

            print('Profiler: init: %s, unit: %s, graph: %s, BFS: %s, attack: %s, r_limit: %s' %
                  (round(self.init_profile, 2), round(self.units_profile, 2), round(self.graph_profile, 2),
                   round(self.bfs_profile, 2), round(self.attack_profile, 2), round(self.range_profiler, 2)))

            # print('gr_1: %s, gr_2: %s, gr_3: %s, gr_4: %s, gr_5: %s new_gr %s' % (
            #     round(self.gr_1, 2), round(self.gr_2, 2),
            #     round(self.gr_3, 2), round(self.gr_4, 2),
            #     round(self.gr_5, 2), round(self.new_gr, 2)))

            print('Death counter: %s Bonus counter: %s' % (self.DEATH_COUNT, self.BONUS_COUNT))
            print('Current strategy tick is %s, current_graph %s, max graph vertex %s' % (self.strategy_steps,
                                                                                          self.debug_graph_cells,
                                                                                          self.debug_graph_cells_max))
            print('')

        if self.debug_message:
            print(self.debug_message)
            self.debug_message = None

    def move(self, me: Wizard, world: World, game: Game, move: Move):

        # initialize
        init_timer = time.time()
        if self.strategy_steps == 0:
            self.initialize_strategy(game, me, world)
        self.initialize_tick(world=world, game=game, me=me, move=move)
        self.init_profile += time.time() - init_timer

        # visual and text debugger activation
        if debug:
            self.visual_debugger()
            self.print_section()

        # skills learning
        if self.game.skills_enabled:
            self.skills()

        # get all tick information:
        units_timer = time.time()
        self.load_units_in_vicinity()
        self.units_profile += time.time() - units_timer

        # low hp run back
        if self.low_hp_run_back():
            return None

        # bonus collection: if nobody collects in game
        if self.bonus_collector():
            return None

        # range limit function
        range_timer = time.time()
        self.range_limit_flag()
        if self.range_limit():
            self.range_profiler += time.time() - range_timer
            return None
        self.range_profiler += time.time() - range_timer

        # if on the edge of range and nothing triggers
        if self.my_target:
            self.attack_target(self.my_target)

        # check, if stuck
        self.stuck_check()

        # nothing to do - go further + if this is beginning wait for a minion wave
        self.FIGHTING = False

        if self.CURRENT_WAYPOINT_INDEX == self.MINION_STAY[1] and self.strategy_steps < self.MINION_STAY[0]:
            self.NO_MOVE = 0
            return None
        else:
            self.move_to_waypoint(self.next_waypoint())

    # ------ decision tree functions ---------------------------------------

    def initialize_strategy(self, game, me, world):
        random.seed(game.random_seed)
        map_size = game.map_size

        self.respawn = [me.x, me.y]
        self.PREVIOUS_POS = self.respawn

        for tower in world.buildings:
            if tower.x != 400 and tower.y != 3600:
                self.towers.append(tower)

        self.start_positions.append([100, 3700])
        self.start_positions.append([300, 3900])
        self.start_positions.append([200, 3800])
        self.start_positions.append([300, 3800])
        self.start_positions.append([200, 3700])

        self.waypoints_top.append([50, map_size - 50])
        self.waypoints_top.append([map_size - 3800, map_size - 1100])
        self.waypoints_top.append([map_size - 3800, map_size - 1400])
        self.waypoints_top.append([map_size - 3800, map_size - 1800])
        self.waypoints_top.append([map_size - 3800, map_size - 2200])
        self.waypoints_top.append([map_size - 3800, map_size - 2800])  # wait wave
        self.waypoints_top.append([map_size - 3800, map_size - 3200])
        self.waypoints_top.append([map_size - 3550, map_size - 3300])
        self.waypoints_top.append([map_size - 3400, map_size - 3400])  # 8
        self.waypoints_top.append([map_size - 3350, map_size - 3600])
        self.waypoints_top.append([map_size - 3200, map_size - 3800])  # 10
        self.waypoints_top.append([map_size - 2800, map_size - 3800])
        self.waypoints_top.append([map_size - 2400, map_size - 3800])
        self.waypoints_top.append([map_size - 2000, map_size - 3800])
        self.waypoints_top.append([map_size - 1600, map_size - 3800])
        self.waypoints_top.append([map_size - 1200, map_size - 3800])
        self.waypoints_top.append([map_size - 900, map_size - 3800])

        self.waypoints_bot.append([50, map_size - 50])
        self.waypoints_bot.append([map_size - 3100, map_size - 200])
        self.waypoints_bot.append([map_size - 2600, map_size - 200])
        self.waypoints_bot.append([map_size - 2200, map_size - 200])
        self.waypoints_bot.append([map_size - 1800, map_size - 200])
        self.waypoints_bot.append([map_size - 1200, map_size - 200])  # stay here
        self.waypoints_bot.append([map_size - 800, map_size - 200])
        self.waypoints_bot.append([map_size - 700, map_size - 450])
        self.waypoints_bot.append([map_size - 600, map_size - 600])
        self.waypoints_bot.append([map_size - 400, map_size - 650])
        self.waypoints_bot.append([map_size - 200, map_size - 800])
        self.waypoints_bot.append([map_size - 200, map_size - 1200])
        self.waypoints_bot.append([map_size - 200, map_size - 1600])
        self.waypoints_bot.append([map_size - 200, map_size - 2000])
        self.waypoints_bot.append([map_size - 200, map_size - 2400])
        self.waypoints_bot.append([map_size - 200, map_size - 2800])
        self.waypoints_bot.append([map_size - 200, map_size - 3100])

        self.waypoints_mid.append([50, map_size - 50])
        self.waypoints_mid.append([map_size - 3800, map_size - 200])
        self.waypoints_mid.append([map_size - 3800, map_size - 800])
        self.waypoints_mid.append([map_size - 3200, map_size - 800])
        self.waypoints_mid.append([map_size - 3000, map_size - 800])
        self.waypoints_mid.append([map_size - 2850, map_size - 1000])
        self.waypoints_mid.append([map_size - 2750, map_size - 1250])
        self.waypoints_mid.append([map_size - 2500, map_size - 1500])
        self.waypoints_mid.append([map_size - 2250, map_size - 1750])
        self.waypoints_mid.append([map_size - 2000, map_size - 2000])
        self.waypoints_mid.append([map_size - 1850, map_size - 2200])
        self.waypoints_mid.append([map_size - 1500, map_size - 2500])
        self.waypoints_mid.append([map_size - 1250, map_size - 2750])
        self.waypoints_mid.append([map_size - 1000, map_size - 3000])
        self.waypoints_mid.append([map_size - 800, map_size - 3200])
        self.waypoints_mid.append([map_size - 400, map_size - 3600])
        self.waypoints_mid.append([map_size - 200, map_size - 3800])

        self.LAST_WAYPOINT_INDEX = 16

        if self.respawn == self.start_positions[0] or self.respawn == self.start_positions[4] or \
                                                      self.respawn == self.start_positions[2]:
            self.lane = LaneType.TOP
            self.waypoints = self.waypoints_top
        if self.respawn == self.start_positions[1] or self.respawn == self.start_positions[3]:
            self.lane = LaneType.BOTTOM
            self.waypoints = self.waypoints_bot

    def initialize_tick(self, world, game, me, move):
        self.world = world
        self.game = game
        self.me = me
        self.move_ = move
        self.strategy_steps += 1

        self.enemies_in_range = None
        self.wizard, self.building, self.fetish, self.orc = None, None, None, None
        self.ally_in_range = None

        # range limit modify if skills enabled
        self.ENEMIES_RANGE_LIMIT = [
                                    self.me.cast_range,
                                    self.me.cast_range - 10,
                                    330,
                                    200
        ]

        self.check_bonus_will_exist()

        if self.strategy_steps - 1 + self.game.wizard_min_resurrection_delay_ticks == self.world.tick_index or \
           self.strategy_steps - 1 != self.world.tick_index:
            self.WAS_DEAD = True
            self.DEATH_COUNT += 1
            self.CURRENT_WAYPOINT_INDEX = 1
            self.strategy_steps = self.world.tick_index + 1
            print('--------------------------------------')
            print('I was dead %s times' % self.DEATH_COUNT)
            print('--------------------------------------')
            self.MOVE_LOW_HP = 0

        if self.WAS_DEAD:
            lane = self.defense_need()
            self.TICK_OF_LAST_WAY = 0
            self.LAST_WAY = None
            self.CURRENT_WAYPOINT_INDEX = 1
            if lane != self.lane:
                self.lane = lane
                if self.lane == LaneType.TOP:
                    self.waypoints = self.waypoints_top
                if self.lane == LaneType.BOTTOM:
                    self.waypoints = self.waypoints_bot
                if self.lane == LaneType.MIDDLE:
                    self.waypoints = self.waypoints_mid
            print('Switch to defense line %s' % self.lane)

            self.WAS_DEAD = False

        # go back at the beginning for not being stuck with the others
        if self.strategy_steps == 1:
            angle = 0
            if self.respawn == self.start_positions[2]:
                print('Start position #%s %s' % (2, self.respawn))
                angle = self.me.get_angle_to(self.me.x - 100, self.me.y + 100)
                self.MINION_STAY = [1460, 6]
            self.move_.turn = angle
            self.move_.speed = self.game.wizard_backward_speed
            return None
        else:
            if self.strategy_steps < 40:
                angle = 0
                if self.respawn == self.start_positions[2] or self.respawn == self.start_positions[3]:
                    angle = self.me.get_angle_to(100, 3800)
                self.move_.turn = angle
                self.move_.speed = self.game.wizard_backward_speed
                return None

    def load_units_in_vicinity(self):
        self.enemies_in_range = self.get_enemies_in_attack_range()
        self.wizard, self.building, self.fetish, self.orc = self.get_the_closest_of_attack_range(self.enemies_in_range)
        self.ally_in_range = self.get_ally_in_shared_exp_range()

        nearest_enemy_wizard = self.get_closest_or_with_low_hp_enemy_wizard_in_attack_range()
        tower = self.get_tower_in_range()
        if nearest_enemy_wizard:
            self.my_target = nearest_enemy_wizard
        elif tower:
            self.my_target = tower
        else:
            self.my_target = self.get_nearest_target_in_my_visible_range()

        self.debug_attack_target = self.my_target

    def attack_target(self, my_target):
        attack_start = time.time()
        if my_target in self.enemies_in_range['wizard']:
            self.FIGHTING = True
            distance = self.me.get_distance_to(my_target.x, my_target.y)
            if distance - my_target.radius <= self.me.cast_range:
                angle = self.me.get_angle_to(my_target.x, my_target.y)
                self.move_.turn = angle
                if abs(angle) < self.game.staff_sector / 2:
                    if self.me.xp > 2750:
                        if self.me.remaining_cooldown_ticks_by_action[3] == 0:
                            self.move_.action = ActionType.FROST_BOLT
                            self.move_.cast_angle = angle
                            self.move_.min_cast_distance = distance - my_target.radius + self.game.magic_missile_radius
                            self.attack_profile += time.time() - attack_start
                            return True
                    else:
                        if self.me.remaining_cooldown_ticks_by_action[2] == 0:
                            self.move_.action = ActionType.MAGIC_MISSILE
                            self.move_.cast_angle = angle
                            self.move_.min_cast_distance = distance - my_target.radius + self.game.magic_missile_radius

                            self.attack_profile += time.time() - attack_start
                            return True
                else:
                    self.attack_profile += time.time() - attack_start
            else:
                self.attack_profile += time.time() - attack_start
        else:
            self.FIGHTING = True
            distance = self.me.get_distance_to(my_target.x, my_target.y)
            if distance - my_target.radius <= self.me.cast_range:
                angle = self.me.get_angle_to(my_target.x, my_target.y)
                self.move_.turn = angle
                if abs(angle) < self.game.staff_sector / 2:
                    if self.me.remaining_cooldown_ticks_by_action[2] == 0:
                        self.move_.action = ActionType.MAGIC_MISSILE
                        self.move_.cast_angle = angle
                        self.move_.min_cast_distance = distance - my_target.radius + self.game.magic_missile_radius

                        self.attack_profile += time.time() - attack_start
                        return True
                    else:
                        self.attack_profile += time.time() - attack_start
                else:
                    self.attack_profile += time.time() - attack_start
            else:
                self.attack_profile += time.time() - attack_start
            return False

    def stuck_check(self):
        if self.me.x == self.PREVIOUS_POS[0] and self.me.y == self.PREVIOUS_POS[1]:
            self.NO_MOVE += 1
            if self.NO_MOVE > 60:
                self.NO_MOVE = 0

            if self.NO_MOVE >= self.MAX_NO_MOVE * 2:
                self.debug_message = 'I am stuck x2'
                self.move_.strafe_speed = -self.game.wizard_strafe_speed
                if self.my_target:
                    if self.attack_target(self.my_target):
                        return True

            if self.NO_MOVE >= self.MAX_NO_MOVE:
                # self.debug_message = 'I am stuck'
                self.move_.strafe_speed = self.game.wizard_strafe_speed
                if self.my_target:
                    if self.attack_target(self.my_target):
                        return True
        else:
            self.NO_MOVE = 0
        self.PREVIOUS_POS = [self.me.x, self.me.y]

    def low_hp_run_back(self):
        if len(self.enemies_in_range['minion']) == 0 and len(self.enemies_in_range['wizard']) == 0 and len(self.enemies_in_range['building']) == 0:
            if self.MOVE_LOW_HP > 0:
                self.MOVE_LOW_HP -= 1
                self.move_to_waypoint(self.last_waypoint())

                if self.strategy_steps % 20 == 0:
                    self.debug_message = 'Go back - low hp'
                if self.my_target:
                    self.attack_target(self.my_target)
                return True
        else:
            if self.me.life < self.me.max_life * self.LOW_HP_FACTOR[0]:
                if self.me.life < self.me.max_life * self.LOW_HP_FACTOR[1]:
                    if self.me.life < self.me.max_life * 0.12:
                        self.debug_message = 'CRITICAL HP LEVEL'
                    self.MOVE_LOW_HP = 100
                    if self.strategy_steps % 20 == 0:
                        self.debug_message = 'Go back - low hp'
                    self.move_to_waypoint(self.last_waypoint())
                    if self.my_target:
                        self.attack_target(self.my_target)
                        return True

    def bonus_collector(self):
        if self.BONUS_EXIST:
            if self.lane == LaneType.TOP:
                if (self.CURRENT_WAYPOINT_INDEX >= 8) and (self.CURRENT_WAYPOINT_INDEX < 10):
                    self.move_.turn = self.me.get_angle_to(self.BONUS_POINT_TOP[0], self.BONUS_POINT_TOP[1])
                    self.move_.speed = self.game.wizard_forward_speed
                    self.move_.action = ActionType.MAGIC_MISSILE
                    self.move_.cast_angle = self.me.get_angle_to(self.BONUS_POINT_TOP[0], self.BONUS_POINT_TOP[1])
                    self.move_.min_cast_distance = 40
                    return True
                # else:
                #     if (self.CURRENT_WAYPOINT_INDEX > 9) and (self.CURRENT_WAYPOINT_INDEX < 11):
                #         if not self.BONUS_GO:
                #             self.move_to_waypoint(self.waypoints[9])
                #         if self.me.get_distance_to(self.waypoints[9][0], self.waypoints[9][1]) < self.WAYPOINT_RADIUS_NEW:
                #             print('waypoint[9] active: goto bonus')
                #             self.BONUS_GO = True
                #         if self.BONUS_GO:
                #             # self.move_to_waypoint(self.BONUS_POINT_TOP, False)
                #             self.move_.turn = self.me.get_angle_to(self.BONUS_POINT_TOP[0], self.BONUS_POINT_TOP[1])
                #             self.move_.speed = self.game.wizard_forward_speed
                #
                #             self.move_.action = ActionType.MAGIC_MISSILE
                #             self.move_.cast_angle = self.me.get_angle_to(self.BONUS_POINT_TOP[0],
                #                                                          self.BONUS_POINT_TOP[1])
                #             self.move_.min_cast_distance = 40
                #
                #             if self.me.get_distance_to(self.BONUS_POINT_TOP[0], self.BONUS_POINT_TOP[1]) <= 55:
                #                 if self.me.statuses:
                #                     self.BONUS_COUNT += 1
                #                     self.BONUS_GO = False
                #                     self.CURRENT_WAYPOINT_INDEX = 8
                #                     my_status = self.me.statuses[0]
                #                     print(my_status.type, my_status.remaining_duration_ticks)
                #
                #             self.strategy_time += time.time() - start_strategy_execute
                #             return None
                #         self.strategy_time += time.time() - start_strategy_execute
                #         return None

            if self.lane == LaneType.BOTTOM:
                if (self.CURRENT_WAYPOINT_INDEX >= 8) and (self.CURRENT_WAYPOINT_INDEX < 10):
                    self.move_.turn = self.me.get_angle_to(self.BONUS_POINT_BOT[0], self.BONUS_POINT_BOT[1])
                    self.move_.speed = self.game.wizard_forward_speed
                    self.move_.action = ActionType.MAGIC_MISSILE
                    self.move_.cast_angle = self.me.get_angle_to(self.BONUS_POINT_BOT[0], self.BONUS_POINT_BOT[1])
                    self.move_.min_cast_distance = 40
                    return True
                # else:
                #     # collect bonus if at 11 and 12 position
                #     if (self.CURRENT_WAYPOINT_INDEX > 9) and (self.CURRENT_WAYPOINT_INDEX < 11):
                #         if not self.BONUS_GO:
                #             self.move_to_waypoint(self.waypoints[9])
                #         if self.me.get_distance_to(self.waypoints[9][0], self.waypoints[9][1]) < self.WAYPOINT_RADIUS_NEW:
                #             print('waypoint[9] active: goto bonus')
                #             self.BONUS_GO = True
                #         if self.BONUS_GO:
                #             # self.move_to_waypoint(self.BONUS_POINT_TOP, False)
                #             self.move_.turn = self.me.get_angle_to(self.BONUS_POINT_BOT[0], self.BONUS_POINT_BOT[1])
                #             self.move_.speed = self.game.wizard_forward_speed
                #
                #             self.move_.action = ActionType.MAGIC_MISSILE
                #             self.move_.cast_angle = self.me.get_angle_to(self.BONUS_POINT_BOT[0],
                #                                                          self.BONUS_POINT_BOT[1])
                #             self.move_.min_cast_distance = 40
                #
                #             if self.me.get_distance_to(self.BONUS_POINT_BOT[0], self.BONUS_POINT_BOT[1]) <= 55:
                #                 if self.me.statuses:
                #                     self.BONUS_COUNT += 1
                #                     self.BONUS_GO = False
                #                     self.CURRENT_WAYPOINT_INDEX = 8
                #                     my_status = self.me.statuses[0]
                #                     print(my_status.type, my_status.remaining_duration_ticks)
                #
                #             self.strategy_time += time.time() - start_strategy_execute
                #             return None
                #         self.strategy_time += time.time() - start_strategy_execute
                #         return None

    def range_limit_flag(self):
        if self.orc:
            if self.me.get_distance_to(self.orc.x, self.orc.y) <= self.ENEMIES_RANGE_LIMIT[3]:
                self.RANGE_LIMIT_ACTIVE = True
        if self.fetish:
            if self.me.get_distance_to(self.fetish.x, self.fetish.y) <= self.ENEMIES_RANGE_LIMIT[2]:
                self.RANGE_LIMIT_ACTIVE = True
        if self.building:
            if self.me.get_distance_to(self.building.x, self.building.y) <= self.ENEMIES_RANGE_LIMIT[1]:
                self.RANGE_LIMIT_ACTIVE = True
        if self.wizard:
            if self.me.get_distance_to(self.wizard.x, self.wizard.y) <= self.ENEMIES_RANGE_LIMIT[0]:
                self.RANGE_LIMIT_ACTIVE = True

    def range_limit(self):
        if self.RANGE_LIMIT_ACTIVE:
            if self.my_target:
                if self.me.remaining_cooldown_ticks_by_action[2] < 6:
                    if self.attack_target(self.my_target):
                        return True
            if self.me.remaining_cooldown_ticks_by_action[2] >= 6:
                waypoint = self.last_waypoint()
                angle = self.me.get_angle_to(waypoint[0], waypoint[1])
                self.move_.turn = -angle
                self.move_.speed = -self.game.wizard_backward_speed
                self.RANGE_LIMIT_ACTIVE = False
            return True

    def skills(self):
        # hardcoded
        # LVL:
        #   1 = 50
        #   2 = 150
        #   3 = 300
        #   4 = 500
        #   5 = 750
        #   6 = 1050
        #   7 = 1400
        #   8 = 1800
        #   9 = 2250
        #   10= 2750
        #   11= 3300
        #   12= 3900

        if (self.me.xp >= 50) and (self.me.xp < 150):
            self.move_.skill_to_learn = SkillType.RANGE_BONUS_PASSIVE_1
        if (self.me.xp >= 150) and (self.me.xp < 300):
            self.move_.skill_to_learn = SkillType.RANGE_BONUS_AURA_1
        if (self.me.xp >= 300) and (self.me.xp < 500):
            self.move_.skill_to_learn = SkillType.RANGE_BONUS_PASSIVE_2
        if (self.me.xp >= 500) and (self.me.xp < 750):
            self.move_.skill_to_learn = SkillType.RANGE_BONUS_AURA_2
        if (self.me.xp >= 750) and (self.me.xp < 1050):
            self.move_.skill_to_learn = SkillType.ADVANCED_MAGIC_MISSILE

        if (self.me.xp >= 1050) and (self.me.xp < 1400):
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_PASSIVE_1
        if (self.me.xp >= 1400) and (self.me.xp < 1800):
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_AURA_1
        if (self.me.xp >= 1800) and (self.me.xp < 2250):
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_PASSIVE_2
        if (self.me.xp >= 2250) and (self.me.xp < 2750):
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_AURA_2
        if (self.me.xp >= 2750) and (self.me.xp < 3300):
            self.move_.skill_to_learn = SkillType.FROST_BOLT

        # if (self.me.xp >= 50) and (self.me.xp < 150):
        #     self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_PASSIVE_1
        # if (self.me.xp >= 150) and (self.me.xp < 300):
        #     self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_AURA_1
        # if (self.me.xp >= 300) and (self.me.xp < 500):
        #     self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_PASSIVE_2
        # if (self.me.xp >= 500) and (self.me.xp < 750):
        #     self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_BONUS_AURA_2
        # if (self.me.xp >= 750) and (self.me.xp < 1050):
        #     self.move_.skill_to_learn = SkillType.FROST_BOLT
        # if (self.me.xp >= 1050) and (self.me.xp < 1400):
        #     self.move_.skill_to_learn = SkillType.RANGE_BONUS_PASSIVE_1
        # if (self.me.xp >= 1400) and (self.me.xp < 1800):
        #     self.move_.skill_to_learn = SkillType.RANGE_BONUS_AURA_1
        # if (self.me.xp >= 1800) and (self.me.xp < 2250):
        #     self.move_.skill_to_learn = SkillType.RANGE_BONUS_PASSIVE_2
        # if (self.me.xp >= 2250) and (self.me.xp < 2750):
        #     self.move_.skill_to_learn = SkillType.RANGE_BONUS_AURA_2
        # if (self.me.xp >= 2750) and (self.me.xp < 3300):
        #     self.move_.skill_to_learn = SkillType.ADVANCED_MAGIC_MISSILE

        if (self.me.xp >= 3300) and (self.me.xp < 3900):
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_ABSORPTION_PASSIVE_1
        if self.me.xp >= 3900:
            self.move_.skill_to_learn = SkillType.MAGICAL_DAMAGE_ABSORPTION_AURA_1

    # ------ helpers functions ---------------------------------------

    def get_the_closest_of_attack_range(self, enemies):
        # returns
        # enemy_wizard, enemy_tower, enemy_fetish, enemy_orc
        enemy_wizard, enemy_tower, enemy_fetish, enemy_orc = None, None, None, None
        if len(enemies['minion']) == 0 and len(enemies['wizard']) == 0 and len(enemies['building']) == 0:
            return enemy_wizard, enemy_tower, enemy_fetish, enemy_orc
        if len(enemies['wizard']) > 0:
            distance = 700
            enemy_wizard = enemies['wizard'][0]
            for enemy in enemies['wizard']:
                if self.me.get_distance_to(enemy_wizard.x, enemy_wizard.y) < distance:
                    enemy_wizard = enemy
                    distance = self.me.get_distance_to(enemy_wizard.x, enemy_wizard.y)
        if len(enemies['building']) == 1:
            enemy_tower = enemies['building'][0]
        if len(enemies['minion']) > 0:
            enemy_fetish, enemy_orc = None, None
            dist_orc, dist_fetish = 700, 700
            for minion in enemies['minion']:
                if minion.type == MinionType.FETISH_BLOWDART:
                    if self.me.get_distance_to(minion.x, minion.y) < dist_fetish:
                        enemy_fetish = minion
                        dist_fetish = self.me.get_distance_to(enemy_fetish.x, enemy_fetish.y)
                if minion.type == MinionType.ORC_WOODCUTTER:
                    if self.me.get_distance_to(minion.x, minion.y) < dist_orc:
                        enemy_orc = minion
                        dist_orc = self.me.get_distance_to(enemy_orc.x, enemy_orc.y)

        return enemy_wizard, enemy_tower, enemy_fetish, enemy_orc

    def get_enemies_in_attack_range(self):
        enemy_minions, enemy_wizards, enemy_buildings = [], [], []
        for target in self.world.buildings:
            if target.faction == Faction.NEUTRAL or target.faction == self.me.faction:
                continue
            if self.me.get_distance_to(target.x, target.y) <= self.ATTACK_RANGE:
                enemy_buildings.append(target)

        for target in self.world.wizards:
            if target.faction == self.me.faction:
                continue
            if self.me.get_distance_to(target.x, target.y) <= self.ATTACK_RANGE:
                enemy_wizards.append(target)

        for target in self.world.minions:
            if target.faction == Faction.NEUTRAL or target.faction == self.me.faction:
                continue
            if self.me.get_distance_to(target.x, target.y) <= self.ATTACK_RANGE:
                enemy_minions.append(target)
        return {'minion': enemy_minions, 'wizard': enemy_wizards, 'building': enemy_buildings}

    def get_ally_in_shared_exp_range(self):
        ally_minions, ally_wizards, ally_buildings = [], [], []
        for target in self.world.buildings:
            if target.faction == self.me.faction and self.me.get_distance_to(target.x, target.y) <= self.ALLY_RANGE:
                ally_buildings.append(target)

        for target in self.world.wizards:
            if target.faction == self.me.faction and self.me.get_distance_to(target.x, target.y) <= self.ALLY_RANGE:
                ally_wizards.append(target)

        for target in self.world.minions:
            if target.faction == self.me.faction and self.me.get_distance_to(target.x, target.y) <= self.ALLY_RANGE:
                ally_minions.append(target)
        return {'minion': ally_minions, 'wizard': ally_wizards, 'building': ally_buildings}

    def next_waypoint(self):
        if self.CURRENT_WAYPOINT_INDEX == self.LAST_WAYPOINT_INDEX:
            return self.waypoints[self.LAST_WAYPOINT_INDEX]
        if self.me.get_distance_to(self.waypoints[self.CURRENT_WAYPOINT_INDEX][0],
                                   self.waypoints[self.CURRENT_WAYPOINT_INDEX][1]) < self.WAYPOINT_RADIUS_NEW:
            self.CURRENT_WAYPOINT_INDEX += 1
        return self.waypoints[self.CURRENT_WAYPOINT_INDEX]

    def last_waypoint(self):
        if self.CURRENT_WAYPOINT_INDEX == 0:
            return self.waypoints[0]
        if self.me.get_distance_to(self.waypoints[self.CURRENT_WAYPOINT_INDEX - 1][0],
                                   self.waypoints[self.CURRENT_WAYPOINT_INDEX - 1][1]) < self.WAYPOINT_RADIUS_NEW:
            self.CURRENT_WAYPOINT_INDEX -= 1
        return self.waypoints[self.CURRENT_WAYPOINT_INDEX - 1]

    def move_to_waypoint(self, waypoint):
        self.debug_next_waypoint = waypoint
        if self.strategy_steps % 50 == 0:
            print('Waypoint %s, index %s' % (waypoint, self.CURRENT_WAYPOINT_INDEX))

        next_milestone = self.path_finder(waypoint=waypoint)

        # if self.strategy_steps % 50 == 0:
        #     print('Milestone %s' % next_milestone)
        if next_milestone:
            self.debug_next_milestone = next_milestone
            angle = self.me.get_angle_to(next_milestone[0], next_milestone[1])
            self.move_.turn = angle
            self.move_.speed = self.game.wizard_forward_speed
        else:
            print('No answer from pathfinder!')
            if waypoint:
                angle = self.me.get_angle_to(waypoint[0], waypoint[1])
                self.move_.turn = angle
                self.move_.speed = self.game.wizard_forward_speed
            else:
                print('WTF?? no waypoint send to --move_to_waypoint function--')

    def get_closest_or_with_low_hp_enemy_wizard_in_attack_range(self):
        enemy_wizards = []
        for target in self.world.wizards:
            if target.faction == self.me.faction:
                continue
            if self.me.get_distance_to(target.x, target.y) <= self.ATTACK_RANGE:
                enemy_wizards.append(target)
        if len(enemy_wizards) > 0:
            the_closest_enemy_wizard = enemy_wizards[0]
            for enemy in enemy_wizards:
                if self.me.get_distance_to(enemy.x, enemy.y) < self.me.get_distance_to(the_closest_enemy_wizard.x,
                                                                                       the_closest_enemy_wizard.y):
                    the_closest_enemy_wizard = enemy
            for enemy in enemy_wizards:
                if enemy.life < self.LOW_HP_ENEMY_SWITCH and self.me.get_distance_to(enemy.x, enemy.y) < \
                        self.ATTACK_RANGE:
                    return enemy
            return the_closest_enemy_wizard
        else:
            return None

    def get_tower_in_range(self):
        towers = []
        for target in self.world.buildings:
            if target.faction == self.me.faction:
                continue
            if self.me.get_distance_to(target.x, target.y) <= self.ATTACK_RANGE:
                towers.append(target)
        if len(towers) > 0:
            the_closest_tower = towers[0]
            for tower in towers:
                if self.me.get_distance_to(tower.x, tower.y) < self.me.get_distance_to(the_closest_tower.x,
                                                                                       the_closest_tower.y):
                    the_closest_tower = tower
            return the_closest_tower
        else:
            return None

    def get_nearest_target_in_my_visible_range(self):
        targets = []
        for position in self.world.buildings:
            targets.append(position)
        for position in self.world.wizards:
            targets.append(position)
        for position in self.world.minions:
            targets.append(position)

        nearest_target = None
        nearest_target_distance = 700
        for target in targets:
            if target.faction == Faction.NEUTRAL or target.faction == self.me.faction:
                continue
            distance = self.me.get_distance_to(target.x, target.y)
            if distance < nearest_target_distance:
                nearest_target = target
                nearest_target_distance = distance
        return nearest_target

    # ------ heuristics functions ---------------------------------------

    def get_obstacle(self, grid):
        obstacles, objects = [], []

        for target in self.world.buildings:
            objects.append(target)
        for target in self.world.wizards:
            if target.x == self.me.x and target.y == self.me.y:
                continue
            objects.append(target)
        for target in self.world.minions:
            objects.append(target)
        for target in self.world.trees:
            objects.append(target)

        obstacle_extend = 100

        for target in objects:
            if (target.x > grid[0] - obstacle_extend) and (target.x < grid[2] + obstacle_extend) and \
                    (target.y > grid[1] - obstacle_extend) and (target.y < grid[3] + obstacle_extend):
                    if target.x == self.me.x and target.y == self.me.y:
                        continue
                    obstacles.append(target)
        return obstacles

    def obstacle_in_node(self, cell):
        return False

    def path_finder(self, waypoint):
        # new_gr = time.time()
        # path_grid = []
        #
        # start = [self.me.x, self.me.y]
        # if waypoint:
        #     finish = [waypoint[0], waypoint[1]]
        # else:
        #     finish = self.waypoints[self.CURRENT_WAYPOINT_INDEX]
        #
        # path_grid.append(min(start[0], finish[0]) - self.PATH_GRID_EXTEND)  # left-top
        # path_grid.append(min(start[1], finish[1]) - self.PATH_GRID_EXTEND)
        # path_grid.append(max(start[0], finish[0]) + self.PATH_GRID_EXTEND)  # right-bot
        # path_grid.append(max(start[1], finish[1]) + self.PATH_GRID_EXTEND)
        #
        # if path_grid[0] <= 0:
        #     path_grid[0] = 1
        # if path_grid[1] <= 0:
        #     path_grid[1] = 1
        # if path_grid[2] >= 4000:
        #     path_grid[2] = 3999
        # if path_grid[3] >= 4000:
        #     path_grid[3] = 3999
        #
        # step = self.PATH_FINDING_CELL_RADIUS
        #
        # graph_new = IndirectedGraph()
        # for y_line in range(int(path_grid[1] + step + step // 2), int(path_grid[3] - step // 2), step * 2):
        #     for x_line in range(int(path_grid[0] + step + step // 2), int(path_grid[2] - step // 2), step * 2):
        #         if not self.obstacle_in_node([x_line, y_line]):
        #             node_1 = '%s_%s' % (x_line, y_line)
        #             node_2 = '%s_%s' % (x_line - step, y_line - step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line, y_line - step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line + step, y_line - step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line - step, y_line)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line + step, y_line)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line - step, y_line + step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line, y_line + step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line + step, y_line + step)
        #             graph_new.add_connection(node_1, node_2)
        #
        # for y_line in range(int(path_grid[1] + step // 2), int(path_grid[3] - step // 2), step * 2):
        #     for x_line in range(int(path_grid[0] + step + step // 2), int(path_grid[2] - step // 2), step * 2):
        #         if not self.obstacle_in_node([x_line, y_line]):
        #             node_1 = '%s_%s' % (x_line, y_line)
        #             node_2 = '%s_%s' % (x_line - step, y_line)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line + step, y_line)
        #             graph_new.add_connection(node_1, node_2)
        #
        # for y_line in range(int(path_grid[1] + step + step // 2), int(path_grid[3] - step // 2), step * 2):
        #     for x_line in range(int(path_grid[0] + step // 2), int(path_grid[2] - step // 2), step * 2):
        #         if not self.obstacle_in_node([x_line, y_line]):
        #             node_1 = '%s_%s' % (x_line, y_line)
        #             node_2 = '%s_%s' % (x_line, y_line - step)
        #             graph_new.add_connection(node_1, node_2)
        #             node_2 = '%s_%s' % (x_line, y_line + step)
        #             graph_new.add_connection(node_1, node_2)
        #
        # self.new_gr += time.time() - new_gr



        # old working version starts from here ---

        # recalculate option

        if self.TICK_OF_LAST_WAY + self.TIME_PATH_RECALCULATE >= self.strategy_steps:
            if self.LAST_WAY:
                return self.LAST_WAY
        #
        path_forward = time.time()
        gr_1 = time.time()

        start = [self.me.x, self.me.y]
        if waypoint:
            finish = [waypoint[0], waypoint[1]]
        else:
            finish = self.waypoints[self.CURRENT_WAYPOINT_INDEX]

        path_grid = []
        path_grid.append(min(start[0], finish[0]) - self.PATH_GRID_EXTEND)
        path_grid.append(min(start[1], finish[1]) - self.PATH_GRID_EXTEND)
        path_grid.append(max(start[0], finish[0]) + self.PATH_GRID_EXTEND)
        path_grid.append(max(start[1], finish[1]) + self.PATH_GRID_EXTEND)

        if path_grid[0] <= 0:
            path_grid[0] = 1
        if path_grid[1] <= 0:
            path_grid[1] = 1
        if path_grid[2] >= 4000:
            path_grid[2] = 3999
        if path_grid[3] >= 4000:
            path_grid[3] = 3999

        self.debug_path_grid = path_grid
        step = self.PATH_FINDING_CELL_RADIUS
        net_2d = []

        self.gr_1 += time.time() - gr_1
        gr_2 = time.time()

        for net_y in range(int(path_grid[1] + step), int(path_grid[3] - step), int(step * 2)):
            line_x = []
            for net_x in range(int(path_grid[0] + step), int(path_grid[2] - step), int(step * 2)):
                line_x.append([net_x + step, net_y + step])
            net_2d.append(line_x)
        self.gr_2 += time.time() - gr_2

        gr_3 = time.time()
        # get obstacles
        obstacles = self.get_obstacle(path_grid)
        self.debug_obstacles = obstacles
        self.gr_3 += time.time() - gr_3

        gr_4 = time.time()
        # generate grid cell names
        net_2d_name = []
        for line_v in range(0, len(net_2d)):
            net_2d_v = []
            for line_h in range(0, len(net_2d[line_v])):
                net_2d_v.append((line_v + 1) * 100 + line_h)
            net_2d_name.append(net_2d_v)
        self.gr_4 += time.time() - gr_4

        gr_5 = time.time()

        # make connections between elements
        graph = IndirectedGraph()
        for line_v in range(0, len(net_2d)):
            for line_h in range(0, len(net_2d[line_v]) - 1):
                if not self.is_obstacle_in_node(net_2d[line_v][line_h + 1], obstacles, cell_radius=int(step)):
                    graph.add_connection(net_2d_name[line_v][line_h], net_2d_name[line_v][line_h + 1])

        for line_v in range(0, len(net_2d) - 1):
            for line_h in range(0, len(net_2d[line_v])):
                if not self.is_obstacle_in_node(net_2d[line_v + 1][line_h], obstacles, cell_radius=int(step)):
                    graph.add_connection(net_2d_name[line_v][line_h], net_2d_name[line_v + 1][line_h])

        for line_v in range(0, len(net_2d) - 1):
            for line_h in range(0, len(net_2d[line_v]) - 1):
                if not self.is_obstacle_in_node(net_2d[line_v + 1][line_h + 1], obstacles, cell_radius=int(step)):
                    graph.add_connection(net_2d_name[line_v][line_h], net_2d_name[line_v + 1][line_h + 1])

        for line_v in range(len(net_2d) - 1, 1, -1):
            for line_h in range(len(net_2d[line_v]) - 1, 1, -1):
                if not self.is_obstacle_in_node(net_2d[line_v - 1][line_h - 1], obstacles, cell_radius=int(step)):
                    graph.add_connection(net_2d_name[line_v][line_h], net_2d_name[line_v - 1][line_h - 1])

        self.gr_5 += time.time() - gr_5

        # convert start and finish nodes
        start_node = self.return_node(net_2d, [self.me.x, self.me.y], int(step))
        end_node = self.return_node(net_2d, waypoint, int(step))
        self.graph_profile += time.time() - path_forward

        self.debug_graph_cells = len(net_2d)
        if self.debug_graph_cells > self.debug_graph_cells_max:
            self.debug_graph_cells_max = self.debug_graph_cells

        if start_node is None:
            # print('FORWARD: no start waypoint found')
            return self.waypoints[self.CURRENT_WAYPOINT_INDEX]

        if end_node is None:
            # print('FORWARD: no finish waypoint found')
            return self.waypoints[self.CURRENT_WAYPOINT_INDEX]

        bfs_start = time.time()
        next_path = self.bfs(graph_to_search=graph, start=start_node, end=end_node)
        self.bfs_profile += time.time() - bfs_start
        del graph

        # return coordinates based on square name
        if next_path:
            if len(next_path) > 1:
                next_node = next_path[1]
                v_name = (int(next_node) // 100) - 1
                h_name = int(next_node) % 100
                next_coords = net_2d[v_name][h_name]
                self.LAST_WAY = next_coords
                self.TICK_OF_LAST_WAY = self.strategy_steps

                self.debug_view_path = []
                for element in next_path:
                    v_name = (int(element) // 100) - 1
                    h_name = int(element) % 100
                    xy = net_2d[v_name][h_name]
                    self.debug_view_path.append(xy)
                return next_coords
            else:
                return waypoint

    @staticmethod
    def bfs(graph_to_search, start, end):
        queue = [[start]]
        visited = set()
        while queue:
            path = queue.pop(0)
            vertex = path[-1]
            if vertex == end:
                return path
            elif vertex not in visited:
                for current_neighbour in graph_to_search.adjacent_nodes(vertex):
                    new_path = list(path)
                    new_path.append(current_neighbour)
                    queue.append(new_path)
                    if current_neighbour == end:
                        return new_path
                visited.add(vertex)

    @staticmethod
    def is_obstacle_in_node(target_cell, obstacles, cell_radius):
        for obstacle in obstacles:
            squared_dist = (target_cell[0] - obstacle.x) ** 2 + (target_cell[1] - obstacle.y) ** 2
            if squared_dist + obstacle.radius ** 2 <= 1.42 * cell_radius ** 2:
                return True
        return False

    @staticmethod
    def return_node(net, coords, cell_radius):
        if coords is not None:
            for v_line in range(0, len(net)):
                for h_line in range(0, len(net[0])):
                    if (coords[0] >= net[v_line][h_line][0] - cell_radius) and (coords[0] <= net[v_line][h_line][0] + cell_radius) \
                            and (coords[1] >= net[v_line][h_line][1] - cell_radius) and (coords[1] <= net[v_line][h_line][1] + cell_radius):
                        return (v_line + 1) * 100 + h_line
        return None

    def get_a_line_to_push(self):
        we = []
        for target in self.world.wizards:
            if target.faction == self.me.faction:
                if target.x == self.me.x and target.y == self.me.y:
                    continue
                we.append(target)

        top_number, bot_number = 0, 0
        if we:
            for target in we:
                if target.x < 330 and target.y > 3000:
                    top_number += 1
                if target.x > 700 and target.y > 3650:
                    bot_number += 2
        if top_number < self.MIN_PUSH_AMOUNT:
            return LaneType.TOP
        if bot_number < self.MIN_PUSH_AMOUNT:
            return LaneType.BOTTOM
        return LaneType.TOP

    def defense_need(self):
        towers = []
        for tower in self.world.buildings:
            if tower.faction == self.me.faction:
                if tower.x == 400 and tower.y == 3600:
                    continue
                towers.append(tower)

        top_towers, bot_towers, mid_towers = 0, 0, 0
        for tower in towers:
            if tower.x < 360:
                top_towers += 1
            if tower.y > 3600:
                bot_towers += 1
            if round(tower.x) == 902 or round(tower.x) == 903:
                mid_towers += 1
            if tower.y == 2400:
                mid_towers += 1

        if top_towers == 0:
            return LaneType.TOP
        if bot_towers == 0:
            return LaneType.BOTTOM
        if mid_towers == 0:
            return LaneType.MIDDLE

        return self.lane

    def check_bonus_will_exist(self):
        bonus = [0, 0]
        distance, time_to_arrive = 0, 0

        if self.strategy_steps % self.CREATE_BONUS_TICK == 0:
            self.BONUS_EXIST = True
            print('Bonus is created now!')
            return True

        if self.lane == LaneType.TOP:
            bonus = self.BONUS_POINT_TOP
        if self.lane == LaneType.BOTTOM:
            bonus = self.BONUS_POINT_BOT
        if self.lane == LaneType.MIDDLE:
            self.BONUS_EXIST = False
            return None

        for bonus_ in self.world.bonuses:
            if bonus_.x == bonus[0] and bonus_.y == bonus[1]:
                self.BONUS_EXIST = True
                return None

        # get distance to travel for bonus
        if (self.CURRENT_WAYPOINT_INDEX > 6) and (self.CURRENT_WAYPOINT_INDEX <= 14):
            if (self.CURRENT_WAYPOINT_INDEX > 6) and (self.CURRENT_WAYPOINT_INDEX <= 9):
                distance = self.me.get_distance_to(bonus[0], bonus[1])

            if self.CURRENT_WAYPOINT_INDEX > 9:
                distance = self.me.get_distance_to(self.waypoints[10][0], self.waypoints[10][1])
                distance += math.hypot(abs(self.waypoints[9][0] - self.waypoints[10][0]),
                                       abs(self.waypoints[9][1] - self.waypoints[10][1]))
                distance += math.hypot(abs(self.waypoints[9][0] - self.waypoints[8][0]),
                                       abs(self.waypoints[9][1] - self.waypoints[8][1]))
                distance += math.hypot(abs(self.waypoints[8][0] - bonus[0]),
                                       abs(self.waypoints[8][1] - bonus[1]))
            if distance > 0:
                self.debug_distance_to_bonus = distance
                time_to_arrive = distance // self.game.wizard_forward_speed - 20
                self.debug_time_to_arrive = time_to_arrive

            if (self.strategy_steps + round(time_to_arrive)) % 2500 == 0:
                self.BONUS_EXIST = True
                print('--------------------------------------')
                print('BONUS, time to travel %s, distance %s' % (time_to_arrive, distance))
                print('--------------------------------------')

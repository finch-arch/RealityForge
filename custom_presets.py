"""Scenes generated from text or images."""
import json

CUSTOM = {
  "temple": {
    "geoms": "    <geom name=\"temple_wall_l1\" type=\"box\" pos=\"4 -3 3.0\" size=\"3.5 0.3 3.0\" material=\"stone\"/>\n    <geom name=\"temple_wall_l2\" type=\"box\" pos=\"12 -3 2.5\" size=\"3.5 0.3 2.5\" material=\"stone\"/>\n    <geom name=\"temple_wall_l3\" type=\"box\" pos=\"18 -3 2.2\" size=\"2 0.3 2.2\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r1\" type=\"box\" pos=\"5 3 2.5\" size=\"4.5 0.3 2.5\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r2\" type=\"box\" pos=\"14 3 3.5\" size=\"5 0.3 3.5\" material=\"stone\"/>\n    <geom name=\"pillar_l1\" type=\"cylinder\" pos=\"3 -1.3 1.8\" size=\"0.2 1.8\" material=\"stone\"/>\n    <geom name=\"pillar_l2\" type=\"cylinder\" pos=\"7 -1.3 1.8\" size=\"0.2 1.8\" material=\"stone\"/>\n    <geom name=\"pillar_l3\" type=\"cylinder\" pos=\"11 -1.3 2.0\" size=\"0.2 2.0\" material=\"stone\"/>\n    <geom name=\"pillar_l4\" type=\"cylinder\" pos=\"15 -1.3 2.0\" size=\"0.2 2.0\" material=\"stone\"/>\n    <geom name=\"pillar_r1\" type=\"cylinder\" pos=\"4 1.3 1.8\" size=\"0.2 1.8\" material=\"stone\"/>\n    <geom name=\"pillar_r2\" type=\"cylinder\" pos=\"8 1.3 1.8\" size=\"0.2 1.8\" material=\"stone\"/>\n    <geom name=\"pillar_r3\" type=\"cylinder\" pos=\"12 1.3 2.0\" size=\"0.2 2.0\" material=\"stone\"/>\n    <geom name=\"pillar_r4\" type=\"cylinder\" pos=\"16 1.3 2.0\" size=\"0.2 2.0\" material=\"stone\"/>\n    <geom name=\"wooden_stall_l\" type=\"box\" pos=\"9 -4.5 1.2\" size=\"1 0.6 1.2\" material=\"wood\"/>\n    <geom name=\"wooden_stall_r\" type=\"box\" pos=\"10 4.5 1.2\" size=\"1 0.6 1.2\" material=\"wood\"/>\n    <geom name=\"shrine_stupa_l\" type=\"cylinder\" pos=\"6 -5 1.5\" size=\"0.7 1.5\" material=\"stone\"/>\n    <geom name=\"shrine_stupa_r\" type=\"cylinder\" pos=\"17 5 2.0\" size=\"0.9 2.0\" material=\"stone\"/>\n    <geom name=\"stupa_dome_l\" type=\"sphere\" pos=\"6 -5 3.3\" size=\"0.6\" material=\"stone\"/>\n    <geom name=\"stupa_dome_r\" type=\"sphere\" pos=\"17 5 4.4\" size=\"0.75\" material=\"stone\"/>\n    <geom name=\"temple_spire\" type=\"cylinder\" pos=\"19 -5 3.5\" size=\"0.8 3.5\" material=\"stone\"/>\n    <geom name=\"temple_spire_finial\" type=\"sphere\" pos=\"19 -5 7.4\" size=\"0.6\" material=\"stone\"/>\n    <geom name=\"ganges_boat_hull\" type=\"box\" pos=\"8 5.5 0.6\" size=\"1.5 0.4 0.6\" material=\"wood\"/>\n    <geom name=\"banyan_trunk\" type=\"cylinder\" pos=\"20 5 1.5\" size=\"0.5 1.5\" material=\"wood\"/>\n    <geom name=\"banyan_canopy\" type=\"sphere\" pos=\"20 5 3.5\" size=\"1.5\" material=\"wood\"/>\n    <geom name=\"stone_offering_l\" type=\"box\" pos=\"5.5 -4 0.6\" size=\"0.5 0.5 0.6\" material=\"stone\"/>\n    <geom name=\"wood_crate_r\" type=\"box\" pos=\"11 4 0.5\" size=\"0.4 0.4 0.5\" material=\"wood\"/>\n",
    "look": {
      "base_rgb": [
        108,
        104,
        98
      ],
      "dirt_rgb": [
        84,
        80,
        76
      ],
      "contrast": 0.7,
      "sky": [
        "0.36 0.50 0.72",
        "0.84 0.88 0.92"
      ],
      "repeat": "1.5 1.5",
      "prompt": "A sunlit sandstone lane winding through the ghats of Varanasi at golden hour, flanked by weathered temple walls and carved pillars on one side and wooden bazaar stalls, whitewashed stupas with rounded domes, a moored ferry boat, and a broad banyan tree overlooking the Ganges on the other."
    }
  },
  "d_ff5b2e10": {
    "geoms": "    <geom name=\"ghat_wall_l1\" type=\"box\" pos=\"3 -2 1.6\" size=\"2.5 0.3 1.6\" material=\"stone\"/>\n    <geom name=\"ghat_wall_l2\" type=\"box\" pos=\"9 -2 1.8\" size=\"2.5 0.3 1.8\" material=\"stone\"/>\n    <geom name=\"ghat_wall_l3\" type=\"box\" pos=\"15 -2 1.5\" size=\"2.5 0.3 1.5\" material=\"stone\"/>\n    <geom name=\"ghat_wall_l4\" type=\"box\" pos=\"19.2 -2 1.2\" size=\"0.7 0.3 1.2\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r1\" type=\"box\" pos=\"3 2 1.6\" size=\"2.5 0.3 1.6\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r2\" type=\"box\" pos=\"9 2 1.8\" size=\"2.5 0.3 1.8\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r3\" type=\"box\" pos=\"15 2 1.5\" size=\"2.5 0.3 1.5\" material=\"stone\"/>\n    <geom name=\"ghat_wall_r4\" type=\"box\" pos=\"19.2 2 1.2\" size=\"0.7 0.3 1.2\" material=\"stone\"/>\n    <geom name=\"temple_tower_l1\" type=\"cylinder\" pos=\"5 -5.2 3.2\" size=\"0.9 3.2\" material=\"stone\"/>\n    <geom name=\"temple_tower_l2\" type=\"cylinder\" pos=\"12 -6.5 4.2\" size=\"1.2 4.2\" material=\"stone\"/>\n    <geom name=\"temple_tower_l3\" type=\"cylinder\" pos=\"18 -5.5 2.8\" size=\"0.85 2.8\" material=\"stone\"/>\n    <geom name=\"temple_tower_r1\" type=\"cylinder\" pos=\"6 5 3.6\" size=\"1.0 3.6\" material=\"stone\"/>\n    <geom name=\"temple_tower_r2\" type=\"cylinder\" pos=\"13 6.2 4.5\" size=\"1.3 4.5\" material=\"stone\"/>\n    <geom name=\"temple_tower_r3\" type=\"cylinder\" pos=\"17.5 5.3 3.0\" size=\"0.9 3.0\" material=\"stone\"/>\n    <geom name=\"temple_base_l\" type=\"box\" pos=\"12 -6.5 0.9\" size=\"2.6 1.9 0.9\" material=\"stone\"/>\n    <geom name=\"temple_base_r\" type=\"box\" pos=\"13 6.2 0.9\" size=\"2.7 2.0 0.9\" material=\"stone\"/>\n    <geom name=\"temple_dome_l\" type=\"sphere\" pos=\"12 -6.5 0.8\" size=\"0.8\" material=\"stone\"/>\n    <geom name=\"temple_dome_r\" type=\"sphere\" pos=\"13 6.2 0.85\" size=\"0.85\" material=\"stone\"/>\n    <geom name=\"stone_pillar_l1\" type=\"cylinder\" pos=\"2.2 -3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"stone_pillar_l2\" type=\"cylinder\" pos=\"8 -3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"stone_pillar_l3\" type=\"cylinder\" pos=\"16 -3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"stone_pillar_r1\" type=\"cylinder\" pos=\"2.2 3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"stone_pillar_r2\" type=\"cylinder\" pos=\"8 3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"stone_pillar_r3\" type=\"cylinder\" pos=\"16 3.8 2.0\" size=\"0.35 2.0\" material=\"stone\"/>\n    <geom name=\"boat_l1\" type=\"box\" pos=\"5 -9 0.5\" size=\"2.0 0.7 0.5\" material=\"wood\"/>\n    <geom name=\"boat_l2\" type=\"box\" pos=\"11 -10 0.55\" size=\"2.3 0.8 0.55\" material=\"wood\"/>\n    <geom name=\"boat_l3\" type=\"box\" pos=\"17 -9.5 0.5\" size=\"1.8 0.7 0.5\" material=\"wood\"/>\n    <geom name=\"boat_r1\" type=\"box\" pos=\"4.5 9 0.5\" size=\"1.9 0.7 0.5\" material=\"wood\"/>\n    <geom name=\"boat_r2\" type=\"box\" pos=\"10.5 9.8 0.55\" size=\"2.2 0.8 0.55\" material=\"wood\"/>\n    <geom name=\"boat_r3\" type=\"box\" pos=\"17 9.2 0.5\" size=\"1.8 0.7 0.5\" material=\"wood\"/>\n    <geom name=\"wood_mast_l1\" type=\"cylinder\" pos=\"5 -9 1.4\" size=\"0.1 1.4\" material=\"wood\"/>\n    <geom name=\"wood_mast_r1\" type=\"cylinder\" pos=\"10.5 9.8 1.5\" size=\"0.1 1.5\" material=\"wood\"/>\n    <geom name=\"stone_shrine_l\" type=\"box\" pos=\"7 -3.5 0.6\" size=\"0.5 0.5 0.6\" material=\"stone\"/>\n    <geom name=\"stone_shrine_r\" type=\"box\" pos=\"11 3.5 0.6\" size=\"0.5 0.5 0.6\" material=\"stone\"/>\n",
    "look": {
      "base_rgb": [
        108,
        104,
        98
      ],
      "dirt_rgb": [
        84,
        80,
        76
      ],
      "contrast": 0.7,
      "sky": [
        "0.36 0.50 0.72",
        "0.84 0.88 0.92"
      ],
      "repeat": "1.5 1.5",
      "prompt": "A bustling Varanasi riverside ghat at golden hour, weathered sandstone walls and towering temple shikharas rising along the Ganges, wooden boats moored on the murky water, incense smoke drifting past ochre-painted pillars and pilgrims."
    }
  },
  "d_49ae28c3": {
    "geoms": "    <geom name=\"stall_L1\" type=\"box\" pos=\"3 2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_L2\" type=\"box\" pos=\"6.5 2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_L3\" type=\"box\" pos=\"10 2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_L4\" type=\"box\" pos=\"13.5 2.2 0.6\" size=\"1.2 0.6 0.6\" material=\"wood\"/>\n    <geom name=\"stall_L5\" type=\"box\" pos=\"17 2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_R1\" type=\"box\" pos=\"4.5 -2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_R2\" type=\"box\" pos=\"8 -2.2 0.6\" size=\"1.2 0.6 0.6\" material=\"wood\"/>\n    <geom name=\"stall_R3\" type=\"box\" pos=\"11.5 -2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_R4\" type=\"box\" pos=\"15 -2.2 0.55\" size=\"1.2 0.6 0.55\" material=\"wood\"/>\n    <geom name=\"stall_R5\" type=\"box\" pos=\"18.5 -2.2 0.6\" size=\"1.2 0.6 0.6\" material=\"wood\"/>\n    <geom name=\"barrel_L1\" type=\"cylinder\" pos=\"2 1.3 0.5\" size=\"0.3 0.5\" material=\"wood\"/>\n    <geom name=\"barrel_L2\" type=\"cylinder\" pos=\"4.85 1.3 0.55\" size=\"0.3 0.55\" material=\"wood\"/>\n    <geom name=\"barrel_L3\" type=\"cylinder\" pos=\"8.25 1.3 0.5\" size=\"0.35 0.5\" material=\"wood\"/>\n    <geom name=\"barrel_L4\" type=\"cylinder\" pos=\"11.75 1.3 0.45\" size=\"0.3 0.45\" material=\"wood\"/>\n    <geom name=\"barrel_L5\" type=\"cylinder\" pos=\"15.25 1.3 0.55\" size=\"0.3 0.55\" material=\"wood\"/>\n    <geom name=\"barrel_L6\" type=\"cylinder\" pos=\"19 1.3 0.5\" size=\"0.35 0.5\" material=\"wood\"/>\n    <geom name=\"barrel_R1\" type=\"cylinder\" pos=\"2.5 -1.3 0.5\" size=\"0.3 0.5\" material=\"wood\"/>\n    <geom name=\"barrel_R2\" type=\"cylinder\" pos=\"6.25 -1.3 0.55\" size=\"0.35 0.55\" material=\"wood\"/>\n    <geom name=\"barrel_R3\" type=\"cylinder\" pos=\"9.75 -1.3 0.45\" size=\"0.3 0.45\" material=\"wood\"/>\n    <geom name=\"barrel_R4\" type=\"cylinder\" pos=\"13.25 -1.3 0.5\" size=\"0.35 0.5\" material=\"wood\"/>\n    <geom name=\"barrel_R5\" type=\"cylinder\" pos=\"16.75 -1.3 0.55\" size=\"0.3 0.55\" material=\"wood\"/>\n    <geom name=\"post_LF\" type=\"cylinder\" pos=\"1.5 2.9 1.4\" size=\"0.12 1.4\" material=\"stone\"/>\n    <geom name=\"post_LB\" type=\"cylinder\" pos=\"19 2.9 1.4\" size=\"0.12 1.4\" material=\"stone\"/>\n    <geom name=\"post_RF\" type=\"cylinder\" pos=\"3 -2.9 1.4\" size=\"0.12 1.4\" material=\"stone\"/>\n    <geom name=\"post_RB\" type=\"cylinder\" pos=\"20 -2.9 1.4\" size=\"0.12 1.4\" material=\"stone\"/>\n    <geom name=\"crate_L1\" type=\"box\" pos=\"5.5 3.3 0.4\" size=\"0.4 0.4 0.4\" material=\"wood\"/>\n    <geom name=\"crate_L2\" type=\"box\" pos=\"12 3.3 0.45\" size=\"0.4 0.4 0.45\" material=\"wood\"/>\n    <geom name=\"crate_R1\" type=\"box\" pos=\"9 -3.3 0.4\" size=\"0.4 0.4 0.4\" material=\"wood\"/>\n    <geom name=\"crate_R2\" type=\"box\" pos=\"16 -3.3 0.45\" size=\"0.4 0.4 0.45\" material=\"wood\"/>\n    <geom name=\"end_wall\" type=\"box\" pos=\"20.8 0 1.5\" size=\"0.3 3 1.5\" material=\"stone\"/>\n",
    "look": {
      "base_rgb": [
        108,
        104,
        98
      ],
      "dirt_rgb": [
        84,
        80,
        76
      ],
      "contrast": 0.7,
      "sky": [
        "0.36 0.50 0.72",
        "0.84 0.88 0.92"
      ],
      "repeat": "1.5 1.5",
      "prompt": "A narrow medieval market alley at golden hour, wooden trestle stalls lining both sides with weathered oak barrels of grain and ale clustered between them, tall stone pillars framing the entrance, dusty cobblestones underfoot, and a moss-streaked stone wall closing off the far end."
    }
  },
  "ghat": {
    "geoms": "    <geom name=\"pillar_left_near\" type=\"cylinder\" material=\"stone\" pos=\"1.8 2.3 1.6\" size=\"0.35 1.6\"/>\n    <geom name=\"pillar_right_near\" type=\"cylinder\" material=\"stone\" pos=\"1.8 -2.5 1.8\" size=\"0.4 1.8\"/>\n    <geom name=\"pillar_left_mid\" type=\"cylinder\" material=\"stone\" pos=\"6.0 3.2 1.6\" size=\"0.3 1.6\"/>\n    <geom name=\"pillar_left_mid2\" type=\"cylinder\" material=\"stone\" pos=\"9.5 3.6 1.7\" size=\"0.3 1.7\"/>\n    <geom name=\"pillar_left_back\" type=\"cylinder\" material=\"stone\" pos=\"13.0 4.0 1.9\" size=\"0.32 1.9\"/>\n    <geom name=\"wall_left_low\" type=\"box\" material=\"stone\" pos=\"4.5 4.2 0.6\" size=\"2.5 0.4 0.6\"/>\n    <geom name=\"wall_left_1\" type=\"box\" material=\"stone\" pos=\"5.0 5.2 2.0\" size=\"3.5 0.5 2.0\"/>\n    <geom name=\"wall_left_2\" type=\"box\" material=\"stone\" pos=\"10.5 5.6 2.4\" size=\"3.0 0.5 2.4\"/>\n    <geom name=\"wall_left_3\" type=\"box\" material=\"stone\" pos=\"15.5 6.0 2.8\" size=\"3.0 0.6 2.8\"/>\n    <geom name=\"building_left_1\" type=\"box\" material=\"stone\" pos=\"7.5 7.0 3.2\" size=\"2.8 1.0 3.2\"/>\n    <geom name=\"building_left_2\" type=\"box\" material=\"stone\" pos=\"13.0 7.2 3.6\" size=\"2.5 1.2 3.6\"/>\n    <geom name=\"temple_facade\" type=\"box\" material=\"stone\" pos=\"16.5 4.8 4.2\" size=\"2.5 1.4 4.2\"/>\n    <geom name=\"temple_tower\" type=\"box\" material=\"stone\" pos=\"18.8 5.8 5.6\" size=\"1.4 1.8 5.6\"/>\n    <geom name=\"temple_dome\" type=\"sphere\" material=\"stone\" pos=\"18.8 5.8 11.6\" size=\"1.5\"/>\n    <geom name=\"temple_col_1\" type=\"cylinder\" material=\"stone\" pos=\"15.4 3.2 2.2\" size=\"0.3 2.2\"/>\n    <geom name=\"temple_col_2\" type=\"cylinder\" material=\"stone\" pos=\"17.8 3.4 2.4\" size=\"0.32 2.4\"/>\n    <geom name=\"wall_right_low\" type=\"box\" material=\"stone\" pos=\"3.2 -3.0 0.6\" size=\"1.6 0.4 0.6\"/>\n    <geom name=\"boat_1\" type=\"box\" material=\"wood\" pos=\"5.5 -3.6 0.4\" size=\"1.5 0.5 0.4\"/>\n    <geom name=\"boat_2\" type=\"box\" material=\"wood\" pos=\"8.5 -4.0 0.4\" size=\"1.6 0.55 0.4\"/>\n    <geom name=\"boat_3\" type=\"box\" material=\"wood\" pos=\"11.5 -3.9 0.4\" size=\"1.5 0.5 0.4\"/>\n    <geom name=\"boat_4\" type=\"box\" material=\"wood\" pos=\"14.5 -4.5 0.4\" size=\"1.7 0.6 0.4\"/>\n    <geom name=\"boat_5\" type=\"box\" material=\"wood\" pos=\"17.0 -3.6 0.4\" size=\"1.4 0.5 0.4\"/>\n    <geom name=\"rock_river_1\" type=\"sphere\" material=\"stone\" pos=\"7.0 -5.8 0.5\" size=\"0.5\"/>\n    <geom name=\"rock_river_2\" type=\"sphere\" material=\"stone\" pos=\"12.5 -6.2 0.55\" size=\"0.55\"/>\n    <geom name=\"wall_far_back\" type=\"box\" material=\"stone\" pos=\"19.6 4.0 3.0\" size=\"0.4 2.0 3.0\"/>\n",
    "look": {
      "base_rgb": [
        120,
        81,
        42
      ],
      "dirt_rgb": [
        124,
        93,
        60
      ],
      "contrast": 0.75,
      "sky": [
        "0.68 0.57 0.46",
        "0.65 0.49 0.32"
      ],
      "repeat": "1.5 1.5",
      "prompt": "Golden dawn light on the stone ghats of Varanasi with ornate carved pillars framing a robed figure gazing across the misty Ganges toward wooden boats drifting past ancient temple facades."
    }
  },
  "road": {
    "geoms": "    <geom name=\"bush_l1\" type=\"cylinder\" material=\"wood\" pos=\"2.5 1.5 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_l2\" type=\"cylinder\" material=\"wood\" pos=\"4.0 2.0 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_l3\" type=\"cylinder\" material=\"wood\" pos=\"5.5 1.7 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_l4\" type=\"cylinder\" material=\"wood\" pos=\"7.0 2.6 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_l5\" type=\"cylinder\" material=\"wood\" pos=\"9.0 3.0 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_l6\" type=\"cylinder\" material=\"wood\" pos=\"11.0 2.3 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_l7\" type=\"cylinder\" material=\"wood\" pos=\"13.5 3.5 0.4\" size=\"0.35 0.4\"/>\n    <geom name=\"bush_l8\" type=\"cylinder\" material=\"wood\" pos=\"16.0 4.5 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"rock_l1\" type=\"sphere\" material=\"stone\" pos=\"6.5 4.0 0.5\" size=\"0.5\"/>\n    <geom name=\"rock_l2\" type=\"box\" material=\"stone\" pos=\"10.0 4.8 0.5\" size=\"0.5 0.6 0.5\"/>\n    <geom name=\"rock_l3\" type=\"sphere\" material=\"stone\" pos=\"14.0 5.5 0.6\" size=\"0.6\"/>\n    <geom name=\"bush_r1\" type=\"cylinder\" material=\"wood\" pos=\"2.5 -1.5 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_r2\" type=\"cylinder\" material=\"wood\" pos=\"4.0 -2.0 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_r3\" type=\"cylinder\" material=\"wood\" pos=\"5.5 -1.7 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_r4\" type=\"cylinder\" material=\"wood\" pos=\"7.0 -2.6 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_r5\" type=\"cylinder\" material=\"wood\" pos=\"9.0 -3.0 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"bush_r6\" type=\"cylinder\" material=\"wood\" pos=\"11.0 -2.3 0.4\" size=\"0.25 0.4\"/>\n    <geom name=\"bush_r7\" type=\"cylinder\" material=\"wood\" pos=\"13.5 -3.5 0.4\" size=\"0.35 0.4\"/>\n    <geom name=\"bush_r8\" type=\"cylinder\" material=\"wood\" pos=\"16.0 -4.5 0.4\" size=\"0.3 0.4\"/>\n    <geom name=\"rock_r1\" type=\"sphere\" material=\"stone\" pos=\"6.5 -4.0 0.5\" size=\"0.5\"/>\n    <geom name=\"rock_r2\" type=\"box\" material=\"stone\" pos=\"10.0 -4.8 0.5\" size=\"0.5 0.6 0.5\"/>\n    <geom name=\"rock_r3\" type=\"sphere\" material=\"stone\" pos=\"14.0 -5.5 0.6\" size=\"0.6\"/>\n    <geom name=\"ridge_l\" type=\"box\" material=\"stone\" pos=\"22.0 -6.0 1.8\" size=\"2.0 3.0 1.8\"/>\n    <geom name=\"mountain_l\" type=\"sphere\" material=\"stone\" pos=\"23.5 -3.5 2.2\" size=\"2.2\"/>\n    <geom name=\"volcano_c\" type=\"sphere\" material=\"stone\" pos=\"26.0 0.0 3.5\" size=\"3.5\"/>\n    <geom name=\"mountain_r\" type=\"sphere\" material=\"stone\" pos=\"24.0 4.0 2.5\" size=\"2.5\"/>\n    <geom name=\"volcano_far_r\" type=\"sphere\" material=\"stone\" pos=\"27.0 7.5 2.8\" size=\"2.8\"/>\n    <geom name=\"ridge_r\" type=\"box\" material=\"stone\" pos=\"22.5 8.0 1.6\" size=\"2.0 3.0 1.6\"/>\n",
    "look": {
      "base_rgb": [
        66,
        49,
        43
      ],
      "dirt_rgb": [
        103,
        74,
        53
      ],
      "contrast": 0.75,
      "sky": [
        "0.05 0.52 0.70",
        "0.44 0.64 0.72"
      ],
      "repeat": "1.5 1.5",
      "prompt": "A straight two-lane asphalt highway with bright yellow lane markings cuts through a vast Atacama-like high desert of ochre tussock grass and scattered rocks, running toward a distant range of dark volcanic peaks with snow-dusted summits beneath a brilliant blue sky streaked with wispy cirrus clouds."
    }
  },
  "gui_demo": {
    "geoms": "    <geom name=\"mountain_center\" type=\"box\" material=\"stone\" pos=\"19.5 0 2.0\" size=\"3.0 1.5 2.0\"/>\n    <geom name=\"mountain_left1\" type=\"box\" material=\"stone\" pos=\"19.0 -4.5 1.5\" size=\"2.0 1.2 1.5\"/>\n    <geom name=\"mountain_left2\" type=\"box\" material=\"stone\" pos=\"18.5 4.5 1.2\" size=\"1.8 1.0 1.2\"/>\n    <geom name=\"mountain_far_r\" type=\"box\" material=\"stone\" pos=\"19.8 -2.5 1.8\" size=\"1.5 0.8 1.8\"/>\n    <geom name=\"mountain_far_l\" type=\"box\" material=\"stone\" pos=\"19.8 2.5 1.6\" size=\"1.4 0.8 1.6\"/>\n    <geom name=\"shrub_l1\" type=\"sphere\" material=\"wood\" pos=\"3.5 1.4 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l2\" type=\"sphere\" material=\"wood\" pos=\"5.0 2.2 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l3\" type=\"sphere\" material=\"wood\" pos=\"6.8 1.6 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l4\" type=\"sphere\" material=\"wood\" pos=\"8.5 3.0 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l5\" type=\"sphere\" material=\"wood\" pos=\"10.5 2.0 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l6\" type=\"sphere\" material=\"wood\" pos=\"12.0 4.0 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l7\" type=\"sphere\" material=\"wood\" pos=\"14.0 2.5 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_l8\" type=\"sphere\" material=\"wood\" pos=\"15.5 5.0 0.4\" size=\"0.4\"/>\n    <geom name=\"rock_l1\" type=\"cylinder\" material=\"stone\" pos=\"4.5 3.5 0.4\" size=\"0.5 0.4\"/>\n    <geom name=\"rock_l2\" type=\"cylinder\" material=\"stone\" pos=\"9.0 5.0 0.4\" size=\"0.6 0.4\"/>\n    <geom name=\"rock_l3\" type=\"cylinder\" material=\"stone\" pos=\"13.5 4.5 0.4\" size=\"0.5 0.4\"/>\n    <geom name=\"shrub_r1\" type=\"sphere\" material=\"wood\" pos=\"3.5 -1.4 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r2\" type=\"sphere\" material=\"wood\" pos=\"5.2 -2.3 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r3\" type=\"sphere\" material=\"wood\" pos=\"7.0 -1.7 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r4\" type=\"sphere\" material=\"wood\" pos=\"8.8 -3.2 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r5\" type=\"sphere\" material=\"wood\" pos=\"10.8 -2.1 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r6\" type=\"sphere\" material=\"wood\" pos=\"12.5 -4.0 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r7\" type=\"sphere\" material=\"wood\" pos=\"14.2 -2.6 0.4\" size=\"0.4\"/>\n    <geom name=\"shrub_r8\" type=\"sphere\" material=\"wood\" pos=\"15.8 -5.0 0.4\" size=\"0.4\"/>\n    <geom name=\"rock_r1\" type=\"cylinder\" material=\"stone\" pos=\"4.8 -3.6 0.4\" size=\"0.5 0.4\"/>\n    <geom name=\"rock_r2\" type=\"cylinder\" material=\"stone\" pos=\"9.2 -5.0 0.4\" size=\"0.6 0.4\"/>\n    <geom name=\"rock_r3\" type=\"cylinder\" material=\"stone\" pos=\"13.8 -4.5 0.4\" size=\"0.5 0.4\"/>\n    <geom name=\"boulder_l\" type=\"sphere\" material=\"stone\" pos=\"16.5 3.5 0.5\" size=\"0.5\"/>\n    <geom name=\"boulder_r\" type=\"sphere\" material=\"stone\" pos=\"16.8 -3.8 0.5\" size=\"0.5\"/>\n",
    "look": {
      "base_rgb": [
        66,
        49,
        43
      ],
      "dirt_rgb": [
        103,
        74,
        53
      ],
      "contrast": 0.75,
      "sky": [
        "0.05 0.52 0.70",
        "0.44 0.64 0.72"
      ],
      "repeat": "1.5 1.5",
      "prompt": "A sunlit two-lane asphalt highway with bright yellow lane markings stretches dead-straight through a vast Atacama-style high desert of ochre tussock grass and scattered rocks toward a horizon of jagged, snow-dusted volcanic peaks under a deep blue sky streaked with wispy cirrus clouds."
    }
  },
  "my_scene": {
    "geoms": "    <geom name=\"rock_l1\" type=\"sphere\" size=\"0.45\" pos=\"2.5 2.2 0.45\" material=\"stone\"/>\n    <geom name=\"rock_r1\" type=\"sphere\" size=\"0.5\" pos=\"2.8 -2.5 0.5\" material=\"stone\"/>\n    <geom name=\"rock_l2\" type=\"sphere\" size=\"0.6\" pos=\"4.0 3.5 0.6\" material=\"stone\"/>\n    <geom name=\"rock_r2\" type=\"sphere\" size=\"0.55\" pos=\"4.5 -3.2 0.55\" material=\"stone\"/>\n    <geom name=\"boulder_l1\" type=\"box\" size=\"0.6 0.7 0.5\" pos=\"5.5 4.5 0.5\" material=\"stone\"/>\n    <geom name=\"boulder_r1\" type=\"box\" size=\"0.7 0.6 0.6\" pos=\"5.8 -4.2 0.6\" material=\"stone\"/>\n    <geom name=\"rock_l3\" type=\"sphere\" size=\"0.45\" pos=\"6.5 2.5 0.45\" material=\"stone\"/>\n    <geom name=\"rock_r3\" type=\"sphere\" size=\"0.4\" pos=\"7.0 -2.8 0.4\" material=\"stone\"/>\n    <geom name=\"boulder_l2\" type=\"box\" size=\"0.8 0.6 0.7\" pos=\"8.5 5.0 0.7\" material=\"stone\"/>\n    <geom name=\"boulder_r2\" type=\"box\" size=\"0.6 0.8 0.5\" pos=\"8.8 -5.2 0.5\" material=\"stone\"/>\n    <geom name=\"rock_l4\" type=\"sphere\" size=\"0.5\" pos=\"9.5 3.0 0.5\" material=\"stone\"/>\n    <geom name=\"rock_r4\" type=\"sphere\" size=\"0.55\" pos=\"10.0 -3.5 0.55\" material=\"stone\"/>\n    <geom name=\"boulder_l3\" type=\"box\" size=\"0.9 0.7 0.6\" pos=\"11.5 4.5 0.6\" material=\"stone\"/>\n    <geom name=\"boulder_r3\" type=\"box\" size=\"0.7 0.9 0.65\" pos=\"12.0 -4.8 0.65\" material=\"stone\"/>\n    <geom name=\"rock_l5\" type=\"sphere\" size=\"0.5\" pos=\"12.8 2.8 0.5\" material=\"stone\"/>\n    <geom name=\"rock_r5\" type=\"sphere\" size=\"0.45\" pos=\"13.2 -2.6 0.45\" material=\"stone\"/>\n    <geom name=\"boulder_l4\" type=\"box\" size=\"0.8 0.8 0.7\" pos=\"14.5 5.5 0.7\" material=\"stone\"/>\n    <geom name=\"boulder_r4\" type=\"box\" size=\"0.7 0.7 0.6\" pos=\"15.0 -5.0 0.6\" material=\"stone\"/>\n    <geom name=\"rock_l6\" type=\"sphere\" size=\"0.55\" pos=\"16.0 3.2 0.55\" material=\"stone\"/>\n    <geom name=\"rock_r6\" type=\"sphere\" size=\"0.5\" pos=\"16.5 -3.0 0.5\" material=\"stone\"/>\n    <geom name=\"boulder_l5\" type=\"box\" size=\"1.0 0.8 0.8\" pos=\"18.0 4.8 0.8\" material=\"stone\"/>\n    <geom name=\"boulder_r5\" type=\"box\" size=\"0.8 1.0 0.7\" pos=\"18.5 -5.2 0.7\" material=\"stone\"/>\n    <geom name=\"rock_l7\" type=\"sphere\" size=\"0.5\" pos=\"19.5 2.5 0.5\" material=\"stone\"/>\n    <geom name=\"rock_r7\" type=\"sphere\" size=\"0.5\" pos=\"19.8 -2.8 0.5\" material=\"stone\"/>\n",
    "look": {
      "base_rgb": [
        78,
        72,
        54
      ],
      "dirt_rgb": [
        120,
        108,
        91
      ],
      "contrast": 0.75,
      "sky": [
        "0.36 0.56 0.66",
        "0.62 0.75 0.79"
      ],
      "repeat": "3 3",
      "prompt": "A vast empty desert highway of dark asphalt with faded white lane markings stretches straight to a hazy horizon under a cloudless pale-blue sky, flanked by flat rust-orange sand strewn with scattered rocks and low scrub.",
      "skybox_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/sky_my_scene.png",
      "ground_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/rect_my_scene.png"
    }
  },
  "road2": {
    "geoms": "    <geom name=\"bush_l1\" type=\"cylinder\" size=\"0.35 0.4\" pos=\"2.5 2.2 0.4\" material=\"stone\"/>\n    <geom name=\"bush_r1\" type=\"cylinder\" size=\"0.35 0.4\" pos=\"2.8 -2.3 0.4\" material=\"stone\"/>\n    <geom name=\"rock_l1\" type=\"sphere\" size=\"0.5\" pos=\"4.0 3.0 0.5\" material=\"stone\"/>\n    <geom name=\"rock_r1\" type=\"sphere\" size=\"0.5\" pos=\"4.5 -2.8 0.5\" material=\"stone\"/>\n    <geom name=\"bush_l2\" type=\"cylinder\" size=\"0.3 0.4\" pos=\"5.5 2.5 0.4\" material=\"stone\"/>\n    <geom name=\"bush_r2\" type=\"cylinder\" size=\"0.3 0.4\" pos=\"6.0 -3.5 0.4\" material=\"stone\"/>\n    <geom name=\"rock_l2\" type=\"sphere\" size=\"0.6\" pos=\"7.5 4.2 0.6\" material=\"stone\"/>\n    <geom name=\"rock_r2\" type=\"sphere\" size=\"0.55\" pos=\"7.8 -2.5 0.55\" material=\"stone\"/>\n    <geom name=\"bush_l3\" type=\"cylinder\" size=\"0.35 0.45\" pos=\"9.0 2.8 0.45\" material=\"stone\"/>\n    <geom name=\"bush_r3\" type=\"cylinder\" size=\"0.35 0.45\" pos=\"9.5 -3.8 0.45\" material=\"stone\"/>\n    <geom name=\"rock_l3\" type=\"sphere\" size=\"0.7\" pos=\"11.0 3.5 0.7\" material=\"stone\"/>\n    <geom name=\"rock_r3\" type=\"sphere\" size=\"0.65\" pos=\"11.2 -2.6 0.65\" material=\"stone\"/>\n    <geom name=\"bush_l4\" type=\"cylinder\" size=\"0.4 0.5\" pos=\"12.5 5.0 0.5\" material=\"stone\"/>\n    <geom name=\"bush_r4\" type=\"cylinder\" size=\"0.4 0.5\" pos=\"13.0 -4.5 0.5\" material=\"stone\"/>\n    <geom name=\"boulder_l1\" type=\"box\" size=\"0.6 0.6 0.6\" pos=\"14.5 2.8 0.6\" material=\"stone\"/>\n    <geom name=\"boulder_r1\" type=\"box\" size=\"0.6 0.6 0.6\" pos=\"14.8 -3.0 0.6\" material=\"stone\"/>\n    <geom name=\"bush_l5\" type=\"cylinder\" size=\"0.35 0.4\" pos=\"16.0 4.0 0.4\" material=\"stone\"/>\n    <geom name=\"bush_r5\" type=\"cylinder\" size=\"0.35 0.4\" pos=\"16.5 -5.5 0.4\" material=\"stone\"/>\n    <geom name=\"foothill_l\" type=\"box\" size=\"1.8 1.5 1.6\" pos=\"18.5 4.5 1.6\" material=\"stone\"/>\n    <geom name=\"foothill_r\" type=\"box\" size=\"1.8 1.5 1.5\" pos=\"18.8 -4.2 1.5\" material=\"stone\"/>\n    <geom name=\"mountain_l\" type=\"box\" size=\"2.0 2.0 2.5\" pos=\"20.0 6.5 2.5\" material=\"stone\"/>\n    <geom name=\"mountain_r\" type=\"box\" size=\"2.2 2.2 2.8\" pos=\"20.0 -6.8 2.8\" material=\"stone\"/>\n    <geom name=\"mountain_far_l\" type=\"box\" size=\"1.5 1.5 2.2\" pos=\"19.5 2.8 2.2\" material=\"stone\"/>\n    <geom name=\"mountain_far_r\" type=\"box\" size=\"1.5 1.5 2.0\" pos=\"19.5 -2.5 2.0\" material=\"stone\"/>\n",
    "look": {
      "base_rgb": [
        66,
        49,
        43
      ],
      "dirt_rgb": [
        103,
        74,
        53
      ],
      "contrast": 0.75,
      "sky": [
        "0.05 0.52 0.70",
        "0.44 0.64 0.72"
      ],
      "repeat": "0.0417 0.0417",
      "prompt": "A long empty asphalt highway with a yellow center line stretches straight across a sunlit Atacama-style desert plateau of golden scrub grass and scattered rocks toward a distant range of dark volcanic peaks under a brilliant blue sky with wispy cirrus clouds.",
      "skybox_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/sky_road2.png",
      "ground_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/rect_road2.png"
    }
  },
  "road_clean": {
    "geoms": "    <geom name=\"rock_left_1\" type=\"sphere\" size=\"0.45\" pos=\"6.0 5.2 0.45\" material=\"stone\"/>\n    <geom name=\"rock_left_2\" type=\"sphere\" size=\"0.42\" pos=\"13.5 5.8 0.42\" material=\"stone\"/>\n    <geom name=\"rock_right_1\" type=\"sphere\" size=\"0.44\" pos=\"9.0 -5.5 0.44\" material=\"stone\"/>\n    <geom name=\"rock_right_2\" type=\"sphere\" size=\"0.40\" pos=\"17.0 -5.0 0.40\" material=\"stone\"/>\n",
    "look": {
      "base_rgb": [
        66,
        49,
        43
      ],
      "dirt_rgb": [
        103,
        74,
        53
      ],
      "contrast": 0.75,
      "sky": [
        "0.05 0.52 0.70",
        "0.44 0.64 0.72"
      ],
      "repeat": "0.12 0.12",
      "prompt": "A dead-straight asphalt highway with bright yellow centre lines runs through a flat, empty Atacama-style desert of golden scrub toward distant snow-capped volcanic peaks under a deep blue sky.",
      "skybox_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/sky_road_clean.png",
      "ground_file": "/home/finch/Vishal_project/inception/inception-hackathon/out/textures/gnd_road_clean.png",
      "extra_assets": "    <texture type=\"2d\" name=\"roadtex\" file=\"/home/finch/Vishal_project/inception/inception-hackathon/out/textures/rect_road_clean.png\"/>\n    <material name=\"roadmat\" texture=\"roadtex\" texrepeat=\"2.50 1\"/>\n",
      "extra_geoms": "    <geom name=\"road_strip\" type=\"box\" pos=\"20 0 0.012\" size=\"30 6.12 0.01\" material=\"roadmat\" contype=\"0\" conaffinity=\"0\"/>\n"
    }
  }
}

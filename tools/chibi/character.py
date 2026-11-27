"""Chibi character construction for the JIANMO viewer.

The four characters share one chibi skeleton (about three heads tall) and
differ in hair volume, colours, accessories and instruments. Everything is
generated in code, so the assets can be rebuilt without a DCC tool.

Layout is Y-up with the character facing +Z.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .mesh import (
    trs,
    Mesh, blade, catmull_rom, cone, cylinder, revolve, slab_from_outline,
    smooth_normals, solidify_patch, sphere_at, superellipsoid, torus, tube,
    uv_sphere, _axis_angle,
)

TAU = math.pi * 2.0

# --------------------------------------------------------------------------
# proportions
# --------------------------------------------------------------------------
GROUND = 0.00
SHOLE_TOP = 0.105
ANKLE_Y = 0.135
KNEE_Y = 0.455
HIP_Y = 0.855
WAIST_Y = 0.930
CHEST_Y = 1.080
SHOULDER_Y = 1.160
NECK_Y = 1.205
CHIN_Y = 1.268

HEAD_CY = 1.462
HEAD_RX = 0.256
HEAD_RY = 0.276
HEAD_RZ = 0.246

SHOULDER_X = 0.128
HIP_X = 0.058

# the hairline sits above the brows
HAIRLINE_THETA = 1.00

# material slot order -- one entry per PBR material in the exported GLB
MAT_KEYS = [
    "skin", "hair", "hair_tip", "eye_white", "iris", "pupil", "lash",
    "blush", "mouth", "uniform", "collar", "tie", "sock", "shoe",
    "instrument_body", "instrument_neck", "instrument_accent", "metal",
    "drum_shell", "cymbal", "stick", "strap",
]
MAT = {key: i for i, key in enumerate(MAT_KEYS)}


@dataclass
class CharacterSpec:
    """Everything that differs between the four characters."""

    id: str
    name: str
    filename: str

    # colours
    skin: str = "#f6d3b6"
    hair: str = "#c9a7c8"
    hair_tip: str = "#d8b9d6"
    iris: str = "#8c4a3a"
    uniform: str = "#222c4d"
    collar: str = "#f4f2ee"
    tie: str = "#2b3a63"
    shoe: str = "#4a3527"
    sock: str = "#f2f0ea"
    blush: str = "#f2a0a0"
    mouth: str = "#8c3a3a"
    lash: str = "#3a2a34"
    instrument_body: str = "#f2f0ea"
    instrument_accent: str = "#e6ded0"
    drum_shell: str = "#f0f0e4"
    hair_tie: str = "#e8b7c6"

    # face
    eye_y: float = HEAD_CY - 0.012
    eye_x: float = 0.104
    eye_size: float = 0.058
    brow_angle: float = -6.0
    brow_lift: float = 0.0
    mouth_width: float = 0.030

    # hair
    hair_volume: float = 1.055
    hair_theta_end: float = 1.00        # hairline depth at the front
    hair_back_depth: float = 0.80       # extra depth around the back
    hair_length: float = 0.36           # how far the hair hangs at the back
    hair_strands: float = 16.0          # grooves carved into the hanging hair
    hair_strand_depth: float = 0.030
    fringe_span: float = 1.42           # half-angle of the fringe across the brow
    fringe_points: float = 7.0          # number of fringe points
    fringe_tip: float = 1.34            # shortest fringe tip angle
    fringe_drop: float = 0.15           # how much longer the longest tips are
    bang_cover_side: int = 0            # -1 / 0 / +1: side whose fringe drops lower
    bang_cover_theta: float = 1.78
    bang_cover_phi: float = 0.55        # azimuth where the cover is strongest
    bang_cover_width: float = 0.50
    side_lock: bool = True
    side_lock_phi: float = 1.30
    side_lock_theta: float = 2.05
    twin_tail: bool = False
    twin_tail_height: float = 0.0
    twin_tail_length: float = 0.34
    twin_tail_spread: float = 0.055
    ahoge: bool = False
    ahoge_length: float = 0.16
    ahoge_phi: float = 0.22

    # props
    instrument: str = "none"        # guitar | bass | jaguar | drums | none
    accessory: str = "none"         # hairpin | bow | headband | none


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _tri_wave(phi: float, periods: int) -> float:
    """Triangle wave in [-1, 1]; used for skirt pleats."""
    x = (phi * periods) / TAU
    frac = x - math.floor(x)
    return 4.0 * abs(frac - 0.5) - 1.0


def head_surface(x: float, y: float, bulge: float = 0.0):
    """Point on the head ellipsoid for a given (x, y), plus the outward normal."""
    hx = (x / HEAD_RX) ** 2
    hy = ((y - HEAD_CY) / HEAD_RY) ** 2
    hz = max(0.0, 1.0 - hx - hy)
    z = HEAD_RZ * math.sqrt(hz)
    n = np.array([x / (HEAD_RX ** 2), (y - HEAD_CY) / (HEAD_RY ** 2), z / (HEAD_RZ ** 2)])
    n = n / max(np.linalg.norm(n), 1e-12)
    p = np.array([x, y, z]) + n * bulge
    return p, n


def _chord(phi, theta, scale=1.0):
    """Point on the head ellipsoid at azimuth ``phi`` and elevation ``theta``.

    Azimuth is measured from the front: phi = 0 faces +Z, phi = +pi/2 is the
    character's right (+X) and phi = pi is the back of the head.
    Accepts scalars or arrays.
    """
    phi = np.asarray(phi, dtype=np.float64)
    theta = np.asarray(theta, dtype=np.float64)
    st, ct = np.sin(theta), np.cos(theta)
    return np.stack([
        HEAD_RX * scale * st * np.sin(phi),
        HEAD_CY + HEAD_RY * scale * ct,
        HEAD_RZ * scale * st * np.cos(phi),
    ], axis=-1)


def _quad_bezier(p0, p1, p2, t):
    t = np.asarray(t)[:, None]
    return ((1 - t) ** 2 * np.asarray(p0)
            + 2 * (1 - t) * t * np.asarray(p1)
            + t ** 2 * np.asarray(p2))


def _align_to(direction):
    """4x4 rotation mapping +Y onto ``direction``."""
    d = np.asarray(direction, dtype=np.float64)
    d = d / max(np.linalg.norm(d), 1e-12)
    up = np.array([0.0, 1.0, 0.0])
    axis = np.cross(up, d)
    s = float(np.linalg.norm(axis))
    c = float(np.dot(up, d))
    if s < 1e-9:
        if c > 0:
            return np.eye(4)
        m = np.eye(4)
        m[1, 1] = -1.0
        m[0, 0] = -1.0
        return m
    axis /= s
    rot = np.eye(4)
    rot[:3, :3] = _axis_angle(axis, math.atan2(s, c))
    return rot


# --------------------------------------------------------------------------
# body parts
# --------------------------------------------------------------------------
def build_head(spec: CharacterSpec) -> Mesh:
    head = uv_sphere(HEAD_RX, HEAD_RY, HEAD_RZ, 72, 52, MAT["skin"], "head")
    head = head.translated((0.0, HEAD_CY, 0.0))

    def chin_taper(v):
        out = v.copy()
        t = np.clip((CHIN_Y - 0.03 - v[:, 1]) / 0.20, 0.0, 1.0)
        shrink = 1.0 - 0.30 * (t ** 1.6)
        out[:, 0] *= shrink
        out[:, 2] *= (1.0 - 0.22 * (t ** 1.6))
        out[:, 1] = v[:, 1] - 0.012 * (t ** 2)
        return out

    return head.warp(chin_taper)


def build_neck(spec: CharacterSpec) -> Mesh:
    neck = cylinder(0.056, 0.13, 28, MAT["skin"], "neck")
    return neck.translated((0, NECK_Y - 0.035, 0))


def build_torso(spec: CharacterSpec) -> Mesh:
    profile = [
        (0.000, 1.245),
        (0.060, 1.242),
        (0.110, 1.228),
        (0.140, 1.198),
        (0.152, 1.150),
        (0.147, 1.090),
        (0.131, 1.020),
        (0.122, 0.958),
        (0.130, 0.892),
        (0.124, 0.862),
        (0.000, 0.845),
    ]
    torso = revolve(profile, 72, MAT["uniform"], "torso")
    return torso.scaled((1.0, 1.0, 0.74))


def build_skirt(spec: CharacterSpec) -> Mesh:
    profile = [
        (0.128, 0.905),
        (0.152, 0.864),
        (0.172, 0.800),
        (0.186, 0.718),
        (0.194, 0.664),
        (0.186, 0.657),
        (0.178, 0.664),
        (0.170, 0.718),
        (0.156, 0.800),
        (0.136, 0.864),
        (0.116, 0.905),
        (0.128, 0.905),
    ]
    skirt = revolve(profile, 128, MAT["uniform"], "skirt",
                    radial_mod=lambda phi: 1.0 + 0.085 * _tri_wave(phi, 16),
                    cap_bottom=False, cap_top=False)
    return skirt.scaled((1.0, 1.0, 0.82))


def build_leg(spec: CharacterSpec, side: int) -> list:
    hip = (side * HIP_X, HIP_Y, 0.0)
    knee = (side * (HIP_X + 0.006), KNEE_Y, 0.006)
    ankle = (side * (HIP_X + 0.010), ANKLE_Y, 0.0)

    parts = [
        tube([hip, (side * 0.066, 0.66, 0.004), knee], [0.066, 0.058, 0.050], 26,
             MAT["skin"], "thigh"),
        tube([knee, (side * 0.064, 0.28, 0.0), ankle], [0.050, 0.042, 0.037], 24,
             MAT["skin"], "shin"),
        tube([(side * 0.064, 0.285, 0.0), (side * 0.064, 0.19, 0.0), ankle],
             [0.0455, 0.0415, 0.0385], 24, MAT["sock"], "sock"),
    ]

    shoe = superellipsoid(0.052, 0.050, 0.088, 0.42, 36, 24, MAT["shoe"], "shoe")
    parts.append(shoe.translated((side * 0.064, 0.052, 0.020)))
    sole = superellipsoid(0.055, 0.016, 0.092, 0.25, 36, 12, MAT["shoe"], "sole")
    parts.append(sole.translated((side * 0.064, 0.012, 0.020)))
    return parts


def build_arm(spec: CharacterSpec, side: int, shoulder, elbow, wrist, hand_dir=None) -> list:
    parts = []
    s = np.asarray(shoulder, dtype=np.float64)
    e = np.asarray(elbow, dtype=np.float64)
    w = np.asarray(wrist, dtype=np.float64)

    parts.append(tube([s, (s + e) * 0.5, e], [0.052, 0.047, 0.043], 24,
                       MAT["skin"], "upper_arm"))
    parts.append(tube([e, (e + w) * 0.5, w], [0.043, 0.037, 0.032], 22,
                       MAT["skin"], "forearm"))

    mid = s + (e - s) * 0.42
    parts.append(tube([s + (e - s) * 0.01, mid, s + (e - s) * 0.56],
                       [0.059, 0.056, 0.052], 24, MAT["uniform"], "sleeve"))

    if hand_dir is None:
        direction = w - e
    else:
        direction = np.asarray(hand_dir, dtype=np.float64)
    direction = direction / max(np.linalg.norm(direction), 1e-12)
    hand = superellipsoid(0.034, 0.040, 0.026, 0.55, 26, 18, MAT["skin"], "hand")
    parts.append(hand.transformed(_align_to(direction)).translated(w + direction * 0.028))

    thumb = superellipsoid(0.012, 0.019, 0.012, 0.6, 16, 12, MAT["skin"], "thumb")
    off = np.array([-side * 0.024, 0.006, 0.008])
    parts.append(thumb.transformed(_align_to(direction)).translated(w + direction * 0.016 + off))
    return parts


# --------------------------------------------------------------------------
# face
# --------------------------------------------------------------------------
def build_face(spec: CharacterSpec) -> list:
    parts = []
    eye_x = spec.eye_x
    eye_y = spec.eye_y
    eye_r = spec.eye_size

    for side in (-1, 1):
        x = side * eye_x
        p, n = head_surface(x, eye_y, 0.0)
        eyeball = uv_sphere(eye_r, eye_r * 1.12, eye_r * 0.80, 34, 26,
                            MAT["eye_white"], "eyeball")
        parts.append(eyeball.translated(p - n * 0.030))

        iris_c = p - n * 0.030 + n * (eye_r * 0.72)
        parts.append(uv_sphere(eye_r * 0.56, eye_r * 0.60, eye_r * 0.22, 30, 22,
                               MAT["iris"], "iris").translated(iris_c))
        parts.append(uv_sphere(eye_r * 0.25, eye_r * 0.27, eye_r * 0.12, 22, 16,
                               MAT["pupil"], "pupil").translated(iris_c + n * (eye_r * 0.17)))

        side_dir = n + np.array([side * 0.45, 0.55, 0.0])
        side_dir /= max(np.linalg.norm(side_dir), 1e-12)
        parts.append(uv_sphere(eye_r * 0.19, eye_r * 0.20, eye_r * 0.12, 16, 12,
                               MAT["eye_white"], "sparkle").translated(
                                   iris_c + side_dir * (eye_r * 0.20)))

        lash_pts = []
        for k in range(13):
            u = k / 12.0
            ang = math.pi * (0.14 + 0.72 * u)
            lash_pts.append(p - n * 0.030 + np.array([
                math.cos(ang) * eye_r * 1.08,
                math.sin(ang) * eye_r * 1.18,
                eye_r * 0.50,
            ]))
        parts.append(tube(lash_pts, np.linspace(eye_r * 0.17, eye_r * 0.08, len(lash_pts)),
                          12, MAT["lash"], "lash"))

        # the brow has to sit on the skull, not float above it
        brow_y = eye_y + eye_r * 1.30 + spec.brow_lift
        brow_p, _ = head_surface(x, brow_y, 0.004)
        brow = superellipsoid(0.036, 0.0075, 0.009, 0.35, 22, 10, MAT["lash"], "brow")
        parts.append(brow.rotated("z", side * (spec.brow_angle + 6.0)).translated(brow_p))

        cheek_p, _ = head_surface(side * (eye_x + 0.050), eye_y - 0.046, 0.0)
        blush = uv_sphere(0.034, 0.019, 0.019, 22, 14, MAT["blush"], "blush")
        parts.append(blush.scaled((1.0, 1.0, 0.45)).translated(cheek_p - np.array([0, 0, 0.004])))

    nose_p, _ = head_surface(0.0, eye_y - 0.046, 0.0)
    parts.append(uv_sphere(0.016, 0.014, 0.014, 20, 14, MAT["skin"], "nose").translated(
        nose_p - np.array([0, 0, 0.008])))

    mouth_p, _ = head_surface(0.0, eye_y - 0.098, 0.0)
    mouth = uv_sphere(spec.mouth_width, 0.010, 0.012, 24, 14, MAT["mouth"], "mouth")
    parts.append(mouth.scaled((1.0, 1.0, 0.5)).translated(mouth_p - np.array([0, 0, 0.006])))
    return parts


# --------------------------------------------------------------------------
# hair
# --------------------------------------------------------------------------
def _wave(x, periods: float):
    """Triangle wave in [0, 1]; used for fringe points and ragged hair tips."""
    y = (np.asarray(x) * periods) % 1.0
    return 1.0 - np.abs(2.0 * y - 1.0)


def build_hair_volume(spec: CharacterSpec) -> Mesh:
    """The main hair mass: a shell over the crown that hangs down at the back.

    A single continuous surface keeps the silhouette smooth; the lower edge
    is left ragged so it reads as hair rather than as a helmet.
    """
    nu, nv = 88, 18
    vol = spec.hair_volume

    def strand(u, v):
        phi = u * TAU
        back = 0.5 - 0.5 * np.cos(phi)           # 0 at the front, 1 at the back
        th_hair = spec.hair_theta_end + spec.hair_back_depth * back
        arc_t = np.clip(v / 0.5, 0.0, 1.0)
        hang_t = np.clip((v - 0.5) / 0.5, 0.0, 1.0)

        theta = th_hair * arc_t
        p = _chord(phi, theta, vol)

        hang = spec.hair_length * back * (0.70 + 0.30 * _wave(phi / math.pi, 9.0))
        # vertical grooves break the hanging mass into readable strands
        groove = (2.0 * _wave(u, spec.hair_strands) - 1.0) * spec.hair_strand_depth
        radial = 1.0 + 0.28 * hang_t + groove * hang_t
        return np.stack([
            p[..., 0] * radial,
            p[..., 1] - hang * hang_t,
            p[..., 2] * radial,
        ], axis=-1)

    u = np.linspace(0.0, 1.0, nu)
    v = np.linspace(0.0, 1.0, nv)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    pts = strand(uu.reshape(-1), vv.reshape(-1)).reshape(nu, nv, 3)
    return solidify_patch(pts, 0.016, MAT["hair"], "hair_volume")


def _scalp_normal(phi, theta):
    """Outward normal of the head ellipsoid at (azimuth, elevation)."""
    st, ct = np.sin(theta), np.cos(theta)
    n = np.stack([
        st * np.sin(phi) / HEAD_RX,
        ct / HEAD_RY,
        st * np.cos(phi) / HEAD_RZ,
    ], axis=-1)
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def build_fringe(spec: CharacterSpec) -> Mesh:
    """A continuous fringe over the forehead, cut into points."""
    nu, nv = 76, 9

    # The fringe is a layer of hair standing on the scalp.  Its root has to
    # clear the *shell* of the hair cap -- otherwise the rim of the cap
    # punches through it and the whole thing reads as a headband -- while
    # its tips have to touch the skin.  Both are achieved by lifting the
    # scalp surface along its own normal instead of scaling the head
    # ellipsoid, which would blow the root up into a hat brim.
    # how far the outside of the hair cap sits above the scalp
    cap_outer = (spec.hair_volume - 1.0) * 0.25 + 0.008
    # the fringe has to clear the cap's rim just before the cap ends
    v_edge = 0.22

    def _lift(v):
        """Height of the fringe above the scalp along its normal.

        The root is tucked *inside* the cap shell so its own rim is hidden,
        it swells just past the cap's rim to cover that rim, and the tips
        come back down onto the skin.  Doing this with a single scale
        factor instead makes the root balloon into a hat brim.
        """
        v = np.asarray(v, dtype=np.float64)
        peak = cap_outer + 0.014
        up = 0.004 + (peak - 0.004) * np.clip(v / v_edge, 0.0, 1.0)
        down = peak - (peak - 0.008) * np.power(
            np.clip((v - v_edge) / (1.0 - v_edge), 0.0, 1.0), 1.2)
        return np.where(v < v_edge, up, down)

    def strand(u, v):
        phi = -spec.fringe_span + u * (2.0 * spec.fringe_span)
        # pointed tips: the longest columns sit at the peaks of the wave
        wave = _wave(u, spec.fringe_points)
        tip_theta = spec.fringe_tip + spec.fringe_drop * wave
        if spec.bang_cover_side:
            # the fringe drops much lower on one side, covering one eye
            toward = phi * spec.bang_cover_side
            blend = np.where(
                toward > 0.0,
                np.exp(-((toward - spec.bang_cover_phi) / spec.bang_cover_width) ** 2),
                0.0,
            )
            cover = spec.bang_cover_theta * (0.60 + 0.40 * wave)
            tip_theta = tip_theta + blend * (np.maximum(cover, tip_theta) - tip_theta)
        root_theta = spec.hair_theta_end - 0.10
        theta = root_theta + (tip_theta - root_theta) * v
        lift = _lift(v)
        return _chord(phi, theta, 1.0) + _scalp_normal(phi, theta) * lift[:, None]

    u = np.linspace(0.0, 1.0, nu)
    v = np.linspace(0.0, 1.0, nv)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    pts = strand(uu.reshape(-1), vv.reshape(-1)).reshape(nu, nv, 3)
    return solidify_patch(pts, 0.018, MAT["hair"], "fringe")


def build_side_locks(spec: CharacterSpec) -> list:
    """Strands framing the face."""
    if not spec.side_lock:
        return []
    parts = []
    for side in (-1, 1):
        phi = side * spec.side_lock_phi
        root = _chord(phi, spec.hair_theta_end - 0.12, spec.hair_volume * 1.02)
        tip = _chord(side * spec.side_lock_phi * 0.94, spec.side_lock_theta, 1.03)
        tip = tip + np.array([side * 0.016, -0.035, 0.0])
        ctrl = root + (tip - root) * 0.5 + np.array([side * 0.024, 0.0, 0.016])
        t = np.linspace(0.0, 1.0, 12)
        path = _quad_bezier(root, ctrl, tip, t)
        width = np.linspace(0.032, 0.009, 12)
        parts.append(blade(path, width, thickness=0.012, mat=MAT["hair"], name="side_lock"))
    return parts


def build_twin_tails(spec: CharacterSpec) -> list:
    """Ponytails hanging from a tie point on each side of the head."""
    if not spec.twin_tail:
        return []
    parts = []
    for side in (-1, 1):
        # The anchor has to sit on the cap's surface *at that height*, not at
        # a fixed radius: a ponytail tied low would otherwise start floating
        # away from the head, and one tied high would sink into it.
        y = HEAD_CY + spec.twin_tail_height
        t = (y - HEAD_CY) / HEAD_RY
        cap = HEAD_RX * spec.hair_volume * math.sqrt(max(0.0, 1.0 - t * t))
        anchor = np.array([side * (cap + 0.014), y, -0.040])
        tip = anchor + np.array([side * spec.twin_tail_spread,
                                 -spec.twin_tail_length, -0.030])
        ctrl = anchor + np.array([side * (spec.twin_tail_spread + 0.018),
                                  -spec.twin_tail_length * 0.45, -0.030])
        t = np.linspace(0.0, 1.0, 14)
        path = _quad_bezier(anchor, ctrl, tip, t)
        width = np.linspace(0.068, 0.018, 14)
        parts.append(blade(path, width, thickness=0.029, mat=MAT["hair"], name="tail"))

        tie = torus(0.040, 0.014, 26, 12, MAT["hair_tip"], "tie")
        parts.append(tie.rotated("x", 16).translated(anchor))
    return parts


def build_hairpin(spec: CharacterSpec) -> list:
    if spec.accessory != "hairpin":
        return []
    p, n = head_surface(spec.eye_x * 1.85, HEAD_CY + 0.075, 0.0)
    pin = superellipsoid(0.028, 0.028, 0.010, 0.5, 20, 14,
                         MAT["instrument_accent"], "hairpin")
    return [pin.translated(p + n * 0.014).rotated("y", 28)]


def build_ahoge(spec: CharacterSpec) -> list:
    """The single stray strand on the crown."""
    if not spec.ahoge:
        return []
    root = _chord(spec.ahoge_phi, 0.16, spec.hair_volume * 1.02)
    ctrl = root + np.array([0.004, spec.ahoge_length * 0.78, 0.046])
    tip = root + np.array([0.006, spec.ahoge_length * 0.86, 0.026])
    t = np.linspace(0.0, 1.0, 10)
    path = _quad_bezier(root, ctrl, tip, t)
    width = np.linspace(0.019, 0.004, 10)
    return [blade(path, width, thickness=0.010, mat=MAT["hair"], name="ahoge")]


def build_hair(spec: CharacterSpec) -> list:
    parts = [build_hair_volume(spec), build_fringe(spec)]
    parts.extend(build_side_locks(spec))
    parts.extend(build_twin_tails(spec))
    parts.extend(build_hairpin(spec))
    parts.extend(build_ahoge(spec))
    return parts


# --------------------------------------------------------------------------
# uniform
# --------------------------------------------------------------------------
def build_collar(spec: CharacterSpec) -> list:
    """Sailor collar: a cape over the shoulders, front lapels and a navy stripe."""
    parts = []

    def cape(u, v):
        u = np.asarray(u)
        v = np.asarray(v)
        phi = 0.58 + u * (TAU - 1.16)        # gap at the front
        front = np.cos(phi)
        r0 = 0.084
        r1 = 0.126 + 0.088 * np.maximum(0.0, -front)
        drop = 0.050 + 0.215 * np.maximum(0.0, -front) ** 0.9
        r = r0 + (r1 - r0) * v
        y = 1.234 - drop * (v ** 1.30)
        return np.stack([r * np.sin(phi), y, r * np.cos(phi)], axis=1)

    parts.append(_param_patch(cape, (0.0, 1.0), (0.0, 0.88), 80, 6, 0.014,
                               MAT["collar"], "collar"))
    parts.append(_param_patch(cape, (0.0, 1.0), (0.86, 1.0), 80, 3, 0.011,
                               MAT["tie"], "collar_stripe", offset=0.005))

    for side in (-1, 1):
        def lapel(u, v, side=side):
            u = np.asarray(u)
            v = np.asarray(v)
            ax = np.array([side * 0.032, 1.222, 0.100])
            bx = np.array([side * 0.124, 1.208, 0.040])
            tip = np.array([side * 0.046, 1.046, 0.112])
            top = ax + (bx - ax) * u.reshape(-1, 1)
            p = top * (1 - v).reshape(-1, 1) + tip * v.reshape(-1, 1)
            return p + np.sin(np.pi * v).reshape(-1, 1) * np.array([0.0, 0.0, 0.014])

        parts.append(_param_patch(lapel, (0.0, 1.0), (0.0, 1.0), 14, 8, 0.012,
                                   MAT["collar"], "lapel"))
        parts.append(_param_patch(lapel, (0.0, 1.0), (0.0, 0.14), 14, 2, 0.010,
                                   MAT["tie"], "lapel_stripe", offset=0.004))
    return parts


def _param_patch(fn, u_range, v_range, nu, nv, thickness, mat, name, offset=0.0):
    """Sample a parametric surface and turn it into a closed slab."""
    u = np.linspace(u_range[0], u_range[1], nu)
    v = np.linspace(v_range[0], v_range[1], nv)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    pts = fn(uu.reshape(-1), vv.reshape(-1)).reshape(nu, nv, 3)
    if offset:
        du = np.gradient(pts, axis=0)
        dv = np.gradient(pts, axis=1)
        nrm = np.cross(du, dv)
        ln = np.linalg.norm(nrm, axis=2, keepdims=True)
        ln[ln == 0] = 1.0
        pts = pts + (nrm / ln) * offset
    return solidify_patch(pts, thickness, mat, name)


def build_neckerchief(spec: CharacterSpec) -> list:
    parts = []
    parts.append(superellipsoid(0.030, 0.024, 0.020, 0.5, 24, 16,
                                MAT["tie"], "knot").translated((0, 1.178, 0.100)))
    for side in (-1, 1):
        wing = superellipsoid(0.052, 0.016, 0.030, 0.45, 26, 14, MAT["tie"], "wing")
        wing = wing.rotated("z", side * 16).rotated("x", -12)
        parts.append(wing.translated((side * 0.052, 1.170, 0.082)))
    return parts


# --------------------------------------------------------------------------
# instruments
# --------------------------------------------------------------------------
def _guitar_outline(kind: str = "guitar") -> np.ndarray:
    """The silhouette of an electric guitar body, drawn as a closed outline.

    A single-cut solid body: a broad lower bout, a pinched waist, a
    smaller upper bout and a heel that the neck bolts into.  The outline is
    mirrored from a half-profile and smoothed, so the shape is the one an
    illustrator would draw rather than a box with rounded corners.
    """
    if kind == "bass":
        half = [(0.000, 0.185), (0.078, 0.158), (0.122, 0.104), (0.134, 0.028),
                (0.120, -0.034), (0.140, -0.104), (0.120, -0.160), (0.058, -0.184),
                (0.000, -0.190)]
    else:
        half = [(0.000, 0.172), (0.074, 0.148), (0.116, 0.098), (0.130, 0.026),
                (0.118, -0.030), (0.134, -0.098), (0.116, -0.152), (0.056, -0.170),
                (0.000, -0.176)]

    control = np.asarray(half, dtype=np.float64)
    right = catmull_rom(control, samples_per_seg=9)[:-1]
    left = right[::-1].copy()
    left[:, 0] *= -1.0
    return np.concatenate([right, left], axis=0)


def build_guitar(spec: CharacterSpec, kind: str = "guitar") -> list:
    """A stylised electric guitar: flat waisted body, neck, hardware, strings."""
    parts = []
    body_color = MAT["instrument_body"]
    neck_len = 0.36 if kind == "bass" else 0.30

    outline = _guitar_outline(kind)
    body = slab_from_outline(outline, thickness=0.038, dome=0.007,
                              mat=body_color, name="guitar_body")
    parts.append(body)

    neck = superellipsoid(0.024, neck_len * 0.5, 0.011, 0.14, 24, 22,
                          MAT["instrument_neck"], "neck")
    parts.append(neck.translated((0.0, 0.150 + neck_len * 0.5, 0.0)))

    head = superellipsoid(0.026, 0.042, 0.011, 0.16, 24, 18,
                          MAT["instrument_neck"], "headstock")
    parts.append(head.rotated("x", -16).translated((0.0, 0.150 + neck_len + 0.026, 0.0)))

    for dy in (-0.018, 0.038):
        parts.append(superellipsoid(0.050, 0.017, 0.009, 0.22, 24, 12,
                                    MAT["instrument_accent"], "pickup").translated(
                                        (0.0, dy, 0.028)))
    parts.append(superellipsoid(0.052, 0.012, 0.009, 0.22, 24, 12,
                                MAT["metal"], "bridge").translated((0.0, -0.072, 0.028)))
    parts.append(superellipsoid(0.030, 0.014, 0.008, 0.22, 24, 12,
                                MAT["metal"], "tailpiece").translated((0.0, -0.112, 0.024)))

    n_strings = 4 if kind == "bass" else 6
    for i in range(n_strings):
        x = (i - (n_strings - 1) / 2.0) * 0.0088
        parts.append(tube([(x, -0.118, 0.038), (x, 0.150 + neck_len + 0.040, 0.018)],
                          [0.0013, 0.0013], 6, MAT["metal"], "string"))
    return parts


def build_drum(spec: CharacterSpec) -> list:
    """A snare drum worn at the waist."""
    parts = [cylinder(0.115, 0.075, 40, MAT["drum_shell"], "snare")]
    parts.append(torus(0.118, 0.010, 40, 12, MAT["metal"], "rim").translated((0, 0.037, 0)))
    parts.append(torus(0.118, 0.010, 40, 12, MAT["metal"], "rim").translated((0, -0.037, 0)))
    parts.append(cylinder(0.112, 0.006, 40, MAT["collar"], "drum_head").translated((0, 0.040, 0)))
    return parts


def build_sticks(spec: CharacterSpec, center, tilt: float = 14.0) -> list:
    """A single drumstick whose butt sits at ``center``."""
    stick = tube([(0, 0, 0), (0.016, 0.100, 0.008)], [0.006, 0.010], 10,
                 MAT["stick"], "stick")
    # rotate first, then translate: the other order spins the stick around
    # the world origin and throws it off the drum
    return [stick.rotated("x", tilt).translated(center)]


# --------------------------------------------------------------------------
# pose + assembly
# --------------------------------------------------------------------------
def _relaxed_arm(side: int) -> tuple:
    """Default relaxed A-pose, expressed as a wrist target."""
    shoulder = np.array([side * SHOULDER_X, SHOULDER_Y - 0.005, 0.006])
    wrist = np.array([side * 0.212, 0.748, 0.036])
    return shoulder, wrist


UPPER_ARM_LEN = 0.228
FOREARM_LEN = 0.218


def _solve_elbow(shoulder, wrist, side: int, l1: float = UPPER_ARM_LEN,
                 l2: float = FOREARM_LEN) -> np.ndarray:
    """Two-link IK: place the elbow so the arm reaches ``wrist``.

    The elbow is pushed outward and back, which is how a chibi arm reads
    when it is holding something in front of the body.
    """
    s = np.asarray(shoulder, dtype=np.float64)
    w = np.asarray(wrist, dtype=np.float64)
    delta = w - s
    d = float(np.linalg.norm(delta))
    if d < 1e-6:
        return s + np.array([side * 0.2, -0.2, 0.0])
    d = min(max(d, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    u = delta / float(np.linalg.norm(delta))

    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))

    hint = np.array([side * 0.75, -0.15, -0.85])
    perp = np.cross(u, hint)
    if float(np.linalg.norm(perp)) < 1e-6:
        perp = np.cross(u, np.array([0.0, 1.0, 0.0]))
    perp /= max(float(np.linalg.norm(perp)), 1e-12)
    return s + u * a + perp * h


def pose_for(spec: CharacterSpec) -> dict:
    """Joint positions for the arms, plus the instrument transform."""
    left_shoulder, left_wrist = _relaxed_arm(-1)
    right_shoulder, right_wrist = _relaxed_arm(1)
    left = [left_shoulder, None, left_wrist]
    right = [right_shoulder, None, right_wrist]
    instrument = {"matrix": None, "parts": []}

    kind = spec.instrument
    if kind in ("guitar", "bass", "jaguar"):
        scale = 0.82
        neck_len = 0.36 if kind == "bass" else 0.30
        # The instrument sits slightly to the character's left so that the
        # neck passes beside the ribbon instead of straight over it.
        if kind == "bass":
            place = np.array([0.148, 0.845, 0.203])
            tilt = 18.0
        elif kind == "jaguar":
            place = np.array([0.142, 0.890, 0.203])
            tilt = 24.0
        else:
            place = np.array([0.142, 0.885, 0.203])
            tilt = 24.0
        matrix = trs(translate=place, rotate=(-10.0, 0.0, tilt),
                     scale=(scale, scale, scale))
        instrument["matrix"] = matrix
        instrument["parts"] = build_guitar(spec, "bass" if kind == "bass" else "guitar")

        left_hand = _apply(matrix, np.array([0.0, 0.150 + neck_len * 0.52, 0.020]))
        right_hand = _apply(matrix, np.array([0.0, -0.085, 0.050]))
        left[2] = left_hand - np.array([0.0, 0.0, 0.026])
        right[2] = right_hand - np.array([0.0, 0.0, 0.026])

    elif kind == "drums":
        drum_center = np.array([0.0, 0.790, 0.210])
        instrument["matrix"] = _compose(drum_center, (0.0, 0.0, 0.0))
        instrument["parts"] = build_drum(spec)
        for side, slot in ((-1, left), (1, right)):
            hand = drum_center + np.array([side * 0.078, 0.118, 0.052])
            slot[2] = hand - np.array([0.0, 0.0, 0.026])
        instrument["sticks"] = [
            build_sticks(spec, drum_center + np.array([side * 0.062, 0.105, 0.048]))
            for side in (-1, 1)
        ]

    left[1] = _solve_elbow(left[0], left[2], -1)
    right[1] = _solve_elbow(right[0], right[2], 1)

    # hands follow the instrument they are holding, not the forearm
    extra = {}
    if kind in ("guitar", "bass", "jaguar"):
        neck_axis = (_apply(matrix, np.array([0.0, 1.0, 0.0]))
                     - _apply(matrix, np.array([0.0, 0.0, 0.0])))
        extra["left_hand_dir"] = neck_axis
    elif kind == "drums":
        extra["left_hand_dir"] = np.array([0.0, 1.0, 0.0])
        extra["right_hand_dir"] = np.array([0.0, 1.0, 0.0])
    return {"left": left, "right": right, "instrument": instrument, **extra}


def _compose(translate, rotate_deg):
    from .mesh import trs
    return trs(translate=translate, rotate=rotate_deg)


def _apply(matrix, point):
    m = np.asarray(matrix, dtype=np.float64)
    p = np.asarray(point, dtype=np.float64)
    return m[:3, :3] @ p + m[:3, 3]


def build_props(spec: CharacterSpec) -> list:
    """Hair, face and instrument -- the parts that stay as regular meshes."""
    parts = list(build_hair(spec))
    parts.extend(build_face(spec))
    pose = pose_for(spec)
    inst = pose["instrument"]
    if inst["parts"]:
        matrix = inst["matrix"]
        parts.extend(part.transformed(matrix) for part in inst["parts"])
        for group in inst.get("sticks", []):
            parts.extend(group)
    return parts


def build_character(spec: CharacterSpec) -> list:
    """Assemble every part of one character."""
    parts: list = []
    parts.append(build_head(spec))
    parts.append(build_neck(spec))
    parts.append(build_torso(spec))
    parts.append(build_skirt(spec))
    for side in (-1, 1):
        parts.extend(build_leg(spec, side))

    pose = pose_for(spec)
    parts.extend(build_arm(spec, -1, *pose["left"], hand_dir=pose.get("left_hand_dir")))
    parts.extend(build_arm(spec, 1, *pose["right"], hand_dir=pose.get("right_hand_dir")))

    parts.extend(build_face(spec))
    parts.extend(build_hair(spec))
    parts.extend(build_collar(spec))
    parts.extend(build_neckerchief(spec))

    inst = pose["instrument"]
    if inst["parts"]:
        matrix = inst["matrix"]
        for part in inst["parts"]:
            parts.append(part.transformed(matrix))
        for stick_group in inst.get("sticks", []):
            parts.extend(stick_group)
    return parts


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
MATERIAL_STYLE = {
    "skin": (0.0, 0.62),
    "hair": (0.0, 0.60),
    "hair_tip": (0.0, 0.62),
    "eye_white": (0.0, 0.24),
    "iris": (0.0, 0.18),
    "pupil": (0.0, 0.30),
    "lash": (0.0, 0.55),
    "blush": (0.0, 0.85),
    "mouth": (0.0, 0.45),
    "uniform": (0.0, 0.78),
    "collar": (0.0, 0.82),
    "tie": (0.0, 0.74),
    "sock": (0.0, 0.86),
    "shoe": (0.0, 0.44),
    "instrument_body": (0.12, 0.20),
    "instrument_neck": (0.0, 0.42),
    "instrument_accent": (0.10, 0.28),
    "metal": (0.95, 0.26),
    "drum_shell": (0.05, 0.32),
    "cymbal": (0.90, 0.22),
    "stick": (0.0, 0.60),
    "strap": (0.0, 0.82),
}


def spec_colour(spec: CharacterSpec, key: str) -> str:
    special = {
        "eye_white": "#faf8f4",
        "pupil": "#241a20",
        "instrument_neck": "#6b4a2f",
        "metal": "#c9c9cf",
        "cymbal": "#d9b558",
        "stick": "#dcb98a",
        "strap": "#2a2a2e",
    }
    if key in special:
        return special[key]
    if key == "hair_tip":
        return getattr(spec, "hair_tip", None) or spec.hair
    return getattr(spec, key, "#cccccc")


def build_materials(spec: CharacterSpec):
    """Material slots in :data:`MAT_KEYS` order."""
    from .glb import Material, hex_to_linear
    mats = []
    for key in MAT_KEYS:
        metallic, roughness = MATERIAL_STYLE.get(key, (0.0, 0.6))
        colour = spec_colour(spec, key)
        mats.append(Material(key, hex_to_linear(colour), metallic, roughness))
    return mats

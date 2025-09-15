import math
import time

import neopixel
import micropython
from machine import Pin


micropython.mem_info()


class ColorF:
    def __init__(self, r, g, b):
        self.r = min(r, 1.0)
        self.g = min(g, 1.0)
        self.b = min(b, 1.0)
        
    def scale_brightness(self, brightness):
        return ColorF(
            self.r * brightness,
            self.g * brightness,
            self.b * brightness,
        )
    
    @property
    def out(self):
        return (
            int(255.0 * self.r),
            int(255.0 * self.g),
            int(255.0 * self.b),
        )
    
    @property
    def is_black(self):
        return self.r <= 0 and self.g <= 0 and self.b <= 0
    
    @classmethod
    def mix(cls, *colors):
        r = 0.0
        g = 0.0
        b = 0.0
        for c in colors:
            r += c.r
            g += c.g
            b += c.b
        n = float(len(colors))
        return ColorF(
            r,
            g,
            b,
        )
    
    def __str__(self):
        return f"r={self.r},g={self.g},b={self.b}"
    

class ColorSource:
    @property
    def color(self):
        raise NotImplementedError("Subclasses must implement color property")
    

class ConstantColor(ColorSource):
    def __init__(self, color):
        self._color = color
        
    @property
    def color(self):
        return self._color


class NeoPixelBlock:
    def __init__(self, np, start, end):
        self.np = np
        self.start = start
        self.end = end

    @property
    def n(self):
        return self.end - self.start

    def __getitem__(self, index):
        if index < 0 or index >= self.n:
            raise IndexError("Index out of range")
        return self.np[self.start + index]

    def __setitem__(self, index, value):
        if index < 0 or index >= self.n:
            raise IndexError("Index out of range")
        self.np[self.start + index] = value

    def fill(self, color):
        for i in range(self.start, self.end):
            self.np[i] = color

    def write(self):
        self.np.write()


class NeoPixelReplicate:
    def __init__(self, *nps):
        self.nps = nps
        self.n = min(np.n for np in nps)

    def __getitem__(self, index):
        if index < 0 or index >= self.n:
            raise IndexError("Index out of range")
        return self.nps[0][index]
    
    def __setitem__(self, index, value):
        if index < 0 or index >= self.n:
            raise IndexError("Index out of range")
        for np in self.nps:
            np[index] = value
    
    def fill(self, color):
        for np in self.nps:
            np.fill(color)

    def write(self):
        for np in self.nps:
            np.write()

class Animation:
    def evaluate(self, t, n):
        raise NotImplementedError("Subclasses must implement evaluate method")


class Timeline:
    def __init__(self):
        self.t0 = time.ticks_ms()

    @property
    def t(self):
        return float(max(time.ticks_diff(time.ticks_ms(), self.t0), 0)) / 1000.0


class BaseRenderer:
    def render(self, t):
        raise NotImplementedError("Subclasses must implement render method")


class Renderer(BaseRenderer):
    def __init__(self, np, animation):
        self.np = np
        self.animation = animation

    def render(self, t):
        t = t % 1.0
        npn = float(self.np.n)
        colors = [self.animation.evaluate(t, float(n) / npn).out for n in range(self.np.n)]
        for idx, color in enumerate(colors):
            self.np[idx] = color


class Renderers(BaseRenderer):
    def __init__(self, *renderers):
        self.renderers = renderers

    def render(self, t):
        for renderer in self.renderers:
            renderer.render(t)


class AnimationFlash(Animation):
    def __init__(self, color_source, a=12.0, b=2.0, c=2.0, d=2.0):
        self.color_source = color_source
        self.a = a
        self.b = b
        self.c = c
        self.d = d

    def evaluate(self, t, n):
        """
        y = min(1 - (⌊ax⌋ mod b), 1 - (⌊cx⌋ mod d))
        """
        # print(f"Evaluating at t={t}")
        # x = t % 1.0
        x = t
        # print(f"x={x}")
        y = min(1.0 - (int(self.a * x) % self.b), 1.0 - (int(self.c * x) % self.d))
        # print(f"y={y}")
        return self.color_source.color.scale_brightness(y)
    

class AnimationSpinner(Animation):
    def __init__(self, color_source):
        self.color_source = color_source

    def evaluate(self, t, n):
        # print(f"Evaluating at t={t}, n={n}")
        color = self.color_source.color
        x = t + n
        # print(f"x={x}")
        y = (x % 1.0) ** 2.0
        # print(f"y={y}")
        return color.scale_brightness(y)
    

class AnimationRainbow(Animation):
    def __init__(self, brightness=1.0):
        self.brightness = brightness

    def evaluate(self, t, n):
        # print(f"Evaluating at t={t}, n={n}")
        x = (t + n) % 1.0
        r = (math.cos(x * 2 * math.pi) + 1.0) / 2.0
        g = (math.cos((x + 1.0/3.0) * 2 * math.pi) + 1.0) / 2.0
        b = (math.cos((x + 2.0/3.0) * 2 * math.pi) + 1.0) / 2.0
        # print(f"y={y}")
        return ColorF(r, g, b).scale_brightness(self.brightness)
    

class TimeShiftedAnimation(Animation):
    def __init__(self, base_animation, time_shift):
        self.base_animation = base_animation
        self.time_shift = time_shift

    def evaluate(self, t, n):
        return self.base_animation.evaluate(t + self.time_shift, n)


class MixedAnimation(Animation):
    def __init__(self, *animations):
        self.animations = animations

    def evaluate(self, t, n):
        return ColorF.mix(*(anim.evaluate(t, n) for anim in self.animations))
    

class SpeedAdjustedAnimation(Animation):
    def __init__(self, base_animation, speed):
        self.base_animation = base_animation
        self.speed = speed

    def evaluate(self, t, n):
        return self.base_animation.evaluate(t * self.speed, n)
    

class ConcatenatedAnimation(Animation):
    def __init__(self, *animations):
        self.animations = animations
        self.durations = [1.0 for _ in animations]
        self.total_duration = sum(self.durations)

    def evaluate(self, t, n):
        t = t % self.total_duration
        cumulative = 0.0
        for anim, dur in zip(self.animations, self.durations):
            if cumulative + dur >= t:
                local_t = t - cumulative
                return anim.evaluate(local_t, n)
            cumulative += dur
        return ColorF(0.0, 0.0, 0.0)  # Fallback to black if something goes wrong


class ReverseAnimation(Animation):
    def __init__(self, base_animation):
        self.base_animation = base_animation

    def evaluate(self, t, n):
        return self.base_animation.evaluate(-t, n)
    

class RemapAnimation(Animation):
    """
    Takes an animation that takes t in [0,1], and an interval [t0, t1].
    Produces a new animation that at time t = 0 evaluates the base animation at t0,
    at time t = 1 evaluates the base animation at t1, and linearly interpolates in between.
    """
    def __init__(self, base_animation, t0, t1):
        self.base_animation = base_animation
        self.t0 = t0
        self.t1 = t1

    def evaluate(self, t, n):
        t_mapped = self.t0 + (self.t1 - self.t0) * t
        return self.base_animation.evaluate(t_mapped, n)
    

class BakedAnimation(Animation):
    def __init__(self, base_animation, t_steps=100, n_steps=100):
        self.base_animation = base_animation
        self.t_steps = t_steps
        self.n_steps = n_steps
        self.cache = [
            [self.base_animation.evaluate(float(t) / float(t_steps), float(n) / float(n_steps))
             for n in range(n_steps)]
            for t in range(t_steps)
        ]

    def evaluate(self, t, n):
        t = t % 1.0
        n = n % 1.0
        t_index = int(t * float(self.t_steps)) % self.t_steps
        n_index = int(n * float(self.n_steps)) % self.n_steps
        return self.cache[t_index][n_index]
    

# Switch pins
pin_r = Pin(12, Pin.IN, Pin.PULL_UP)
pin_b = Pin(13, Pin.IN, Pin.PULL_UP)
pin_y = Pin(14, Pin.IN, Pin.PULL_UP)


# Onboard LED (shows activity)
led = Pin("LED", Pin.OUT)
led_on = True
def toggle_led():
    global led_on
    led.value(1 if led_on else 0)
    led_on = not led_on


# NeoPixel setup
# We have a single NeoPixel output powering two rings of 12 LEDs each.
# We use NeoPixelBlock to "split" the single output into two halves (one per ring),
# and NeoPixelReplicate to mirror the same output to both rings.
n = 12 * 2
p = 5
np = neopixel.NeoPixel(machine.Pin(p), n)


# Animation timeline.
timeline = Timeline()


# Renderer factory functions for different modes.

def make_rainbow_renderer(np):
    rainbow_anim = AnimationRainbow(brightness=0.1)
    np_block1 = NeoPixelBlock(np, 0, n//2)
    np_block2 = NeoPixelBlock(np, n//2, n)
    np_split = NeoPixelReplicate(np_block1, np_block2)
    rainbow_renderer = Renderer(np_split, rainbow_anim)
    return rainbow_renderer


def make_color_spinner_renderer(np, color):
    anim = SpeedAdjustedAnimation(AnimationSpinner(ConstantColor(color)), speed=3.0)
    np_block1 = NeoPixelBlock(np, 0, n//2)
    np_block2 = NeoPixelBlock(np, n//2, n)
    np_split = NeoPixelReplicate(np_block1, np_block2)
    renderer = Renderer(np_split, anim)
    return renderer


def make_color_flash_renderer(np, color):
    flash_anim = SpeedAdjustedAnimation(AnimationFlash(ConstantColor(color)), speed=1.5)
    np_block1 = NeoPixelBlock(np, 0, n//2)
    np_block2 = NeoPixelBlock(np, n//2, n)
    renderer = Renderers(
        Renderer(np_block1, flash_anim),
        Renderer(np_block2, TimeShiftedAnimation(flash_anim, 0.5)),
    )
    return renderer


def make_two_color_flash_renderer(np, color1, color2):
    anim = SpeedAdjustedAnimation(
        ConcatenatedAnimation(
            AnimationFlash(ConstantColor(color1), d=1.0),
            AnimationFlash(ConstantColor(color2), d=1.0),
        ),
        speed=1.5
    )
    baked_anim = BakedAnimation(anim, t_steps=200, n_steps=1)
    np_block1 = NeoPixelBlock(np, 0, n//2)
    np_block2 = NeoPixelBlock(np, n//2, n)
    renderer = Renderers(
        Renderer(
            np_block1, 
            baked_anim
        ),
        Renderer(
            np_block2,
            ReverseAnimation(baked_anim)
        ),
    )
    return renderer


def get_mode():
    r = pin_r.value() == 0
    b = pin_b.value() == 0
    y = pin_y.value() == 0
    if r and b and y:
        return "rainbow"
    elif r and b:
        return "red_blue_flash"
    elif r and y:
        return "red_flash"
    elif b and y:
        return "blue_flash"
    elif r:
        return "red_spinner"
    elif b:
        return "blue_spinner"
    elif y:
        return "yellow_spinner"
    else:
        return "off"


mode = "off"
renderer = None
while True:
    toggle_led()
    new_mode = get_mode()
    if new_mode != mode:
        mode = new_mode
        print(f"Mode changed to {mode}")
        if mode == "rainbow":
            renderer = make_rainbow_renderer(np)
        elif mode == "red_blue_flash":
            renderer = make_two_color_flash_renderer(np, ColorF(1.0, 0.0, 0.0), ColorF(0.0, 0.0, 1.0))
        elif mode == "red_flash":
            renderer = make_color_flash_renderer(np, ColorF(1.0, 0.0, 0.0))
        elif mode == "blue_flash":
            renderer = make_color_flash_renderer(np, ColorF(0.0, 0.0, 1.0))
        elif mode == "yellow_flash":
            renderer = make_color_flash_renderer(np, ColorF(1.0, 0.4, 0.0))
        elif mode == "red_spinner":
            renderer = make_color_spinner_renderer(np, ColorF(1.0, 0.0, 0.0))
        elif mode == "blue_spinner":
            renderer = make_color_spinner_renderer(np, ColorF(0.0, 0.0, 1.0))
        elif mode == "yellow_spinner":
            renderer = make_color_spinner_renderer(np, ColorF(1.0, 0.4, 0.0))
        elif mode == "off":
            renderer = None

    if renderer:
        renderer.render(timeline.t)
        np.write()
    else:
        np.fill((0, 0, 0))
        np.write()
        time.sleep(0.1)

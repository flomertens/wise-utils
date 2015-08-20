'''
Description: Set of class and function that help handle images data from 
different source (jpeg, png, fits, ...)

Created on Feb 22, 2012

@author: fmertens

Requirement: astropy version >= 0.3
'''

import os
import re
import copy
import imghdr
import decimal
import datetime
import numpy as np
import PIL.Image

from scipy import misc
from scipy.ndimage import measurements
from scipy.ndimage.interpolation import rotate, zoom

import astropy.units as u
import astropy.wcs as pywcs
import astropy.io.fits as pyfits
from astropy.coordinates import ICRS
import astropy.cosmology as cosmology
from astropy.time import TimeDelta

from mpl_toolkits.axisartist.grid_helper_curvelinear import GridHelperCurveLinear
from mpl_toolkits.axisartist.grid_finder import FormatterPrettyPrint

import pyregion

RESSOURCE_PATH = os.path.join(os.path.dirname(__file__), 'ressource')

import nputils
import signalutils


GALAXY_GIF_PATH = os.path.join(RESSOURCE_PATH, "aa.gif")

# cosmology.default_cosmology.set(cosmology.WMAP9)


def p2i(xy_pixel):
    ''' Tramsform [[x, y], ...] to [[y, x]...]'''
    return np.array(xy_pixel).T[::-1].T


# NOT USED
# def rectangle(size, nx, ny=None):
#     if not ny:
#         ny = nx
#     img = np.zeros((size, size))
#     a = (size - nx) / 2.
#     b = (size - ny) / 2.
#     img[a:-a, b:-b] = 1
#     return img


def draw_rectangle(array, a, b, value=1):
    x1, x2 = sorted([a[0], b[0]])
    y1, y2 = sorted([a[1], b[1]])
    array[x1:x2 + 1, y1:y2 + 1] = 1

    return array


# NOT USED
# def draw_line(array, p, angle, value=1):
#     angle = angle % 180
#     a, b = p
#     if angle <= 45 or angle > 135:
#         p1 = [0, int(np.round(b - a * np.tan(np.radians(angle))))]
#         p2 = [array.shape[0] - 1, int(np.round(b + (array.shape[0] - a) * np.tan(np.radians(angle))))]
#         return draw_2points_line(array, p1, p2, value)
#     else:
#         angle = angle - 90
#         p1 = [int(np.round(a - b * np.tan(np.radians(angle)))), 0]
#         p2 = [int(np.round(a + (array.shape[1] - b) * np.tan(np.radians(angle)))), array.shape[1] - 1]
#         return draw_2points_line(array, p1, p2, value)


# NOT USED
# def draw_2points_line(inp, a, b, value):
#     x0, y0 = a
#     x1, y1 = b
#     if abs(x1 - x0) > abs(y1 - y0):
#         x = np.arange(x0, x1)
#         y = np.linspace(y0, y1, len(x)).astype(int)
#     else:
#         y = np.arange(y0, y1)
#         x = np.linspace(x0, x1, len(y)).astype(int)
#     inp[x, y] = value
#     return inp


def gaussian(size, nsigma=None, width=None, center=None, center_offset=None, angle=0):
    ''' size_or_data: if 1D, give the shape of the output, a new array will be created.
                      if 2D, draw the gaussian into the data
        angle: in radians '''
    if nsigma is None and width is None:
        raise ValueError("You need to specify either nsigma or width")

    size = nputils.get_pair(size)

    if width is not None:
        width = nputils.get_pair(width)
        sigmax, sigmay = width / (2. * np.sqrt(2 * np.log(2)))
    else:
        nsigma = nputils.get_pair(nsigma)
        sigmax, sigmay = size / nsigma / 2.

    if center is None:
        center = np.floor(size / 2.)
    if center_offset is not None:
        center += nputils.get_pair(center_offset)

    indices = np.indices(np.array(size, dtype=np.int))
    p = [0, 1, center, [sigmax, sigmay], angle]

    return nputils.gaussian_fct(*p)(indices)


def multiple_gaussian(size, heights, widths, centers):
    indicies = np.indices(size)
    indicies = np.expand_dims(indicies, -1)
    indicies = np.repeat(indicies, len(heights), -1)

    x, y = indicies
    center_x, center_y = centers.T
    center_x = center_x[None, None, :]
    center_y = center_y[None, None, :]

    sigma = widths / (2. * np.sqrt(2 * np.log(2)))
    sigmax, sigmay = sigma.T
    sigmax = sigmax[None, None, :]
    sigmay = sigmay[None, None, :]

    u = (x - center_x) ** 2 / (2. * sigmax ** 2) + (y - center_y) ** 2 / (2. * sigmay ** 2)
    g = heights * np.exp(-u)

    return g.sum(axis=-1)


def gaussian_cylinder(size, nsigma=None, width=None, angle=None, center_offset=0):
    if nsigma is None and width is None:
        raise ValueError("You need to specify either nsigma or width")

    sizex, sizey = nputils.get_pair(size)

    if width is not None:
        a = 1 / (2. * np.sqrt(2 * np.log(2)))
        sigma = lambda y: a * nputils.make_callable(width)(y)
    else:
        a = sizex / 2.
        sigma = lambda y: a / nputils.make_callable(nsigma)(y)

    if angle is not None:
        off = center_offset
        center_offset = lambda y: off + np.tan(angle) * y
    else:
        center_offset = nputils.make_callable(center_offset)

    hsx = sizex / 2
    x, y = np.mgrid[-hsx:hsx + sizex % 2, 0:sizey]

    g = np.exp(-(x + center_offset(y)) ** 2 / (2. * sigma(y) ** 2))

    return g


# def ellipsoide(size, a, b=None):
#     if b is None:
#         b = a
#     hs = size / 2
#     a = float(a)
#     b = float(b)
#     x, y = np.mgrid[-hs:hs + size % 2, -hs:hs + size % 2]
#     x = x.astype(np.complex)
#     z = np.sqrt(1 - x ** 2 / a ** 2 - y ** 2 / b ** 2).real
#     return z / z.max()


# def paraboloide(size, a, b):
#     hs = size / 2
#     a = float(a)
#     b = float(b)
#     x, z = np.mgrid[-hs:hs + size % 2, 0:size]
#     x = x.astype(np.complex)
#     y = b * np.sqrt(-x ** 2 / a ** 2 + z).real
#     return y


# def cylinder_fct(size, a, fct):
#     hs = size / 2
#     a = float(a)
#     x, y = np.mgrid[-hs:hs + size % 2, -hs:hs + size % 2]
#     x = x.astype(np.complex)
#     z = np.sqrt(1 - (x + fct(y)) ** 2 / a ** 2).real
#     return z / z.max()


# def cylinder(size, a, angle=0):
#     fct = lambda y: np.tan(angle) * y
#     return cylinder_fct(size, a, fct)


def galaxy():
    gif = PIL.Image.open(GALAXY_GIF_PATH)
    return np.array(list(gif.getdata())).reshape(256, 256)


def lena():
    return misc.lena()


# def function(inp, x1, x2, fct, value):
#     x = np.arange(max(0, x1), min(x2, inp.shape[0]))
#     y = fct(x).astype(int)
#     good = (y >= 0) & (y < inp.shape[1])
#     inp[y[good], x[good]] = value
#     return inp


# def polar_fct(inp, fct, value, center=None, n=1000):
#     if not center:
#         center = np.array(inp.shape) / 2
#     teta = np.linspace(0, 2 * np.pi, n)
#     x = center[0] + fct(teta) * np.cos(teta)
#     y = center[1] + fct(teta) * np.sin(teta)
#     inp[x.astype(int), y.astype(int)] = value
#     return inp


# def sort_img_files(files):
#     if is_fits(files[0]):
#         return fast_sorted_fits(files)
#     return sorted(files)


def get_fits_epoch_fast(file):
    header = FastHeaderReader(file)
    date = nputils.guess_date(header.get_value("DATE-OBS"), ["%Y-%m-%d", "%d/%m/%y"])

    return date


def fast_sorted_fits(files, key="DATE-OBS", start_date=None, end_date=None, filter_dates=None, filter=None):
    ''' Need to have the utility gethead install and in the path '''
    file_date = []
    if filter is None:
        filter = nputils.date_filter(start_date=start_date, end_date=end_date, filter_dates=filter_dates)
    for file in files:
        header = FastHeaderReader(file)
        date = get_fits_epoch_fast(file)
        if not filter(date):
            continue
        file_date.append((file, date))
    file_date = sorted(file_date, key=lambda k: k[1])
    return zip(*file_date)[0]


def is_fits(file):
    ''' check if file is a FITS file'''
    with open(file) as f:
        return f.read(6) == 'SIMPLE'


def guess_and_open(file, fits_extension=0):
    if is_fits(file):
        return FitsImage(file, extension=fits_extension)
    if imghdr.what(file) is not None:
        return PilImage(file)
    raise Exception("No handler to open: %s" % file)


class AbstractBeam(object):

    def __init__(self):
        self._beam = None

    def convolve(self, img, boundary="zero"):
        if self._beam == None:
            self._beam = self.build_beam()
        if isinstance(self._beam, tuple):
            c = nputils.convolve(img, self._beam[0], mode='same', boundary=boundary, axis=0) 
            return nputils.convolve(c, self._beam[1], mode='same', boundary=boundary, axis=1) 
        return nputils.convolve(img, self._beam, mode='same', boundary=boundary)

    def build_beam(self):
        raise NotImplementedError()

    def set_header(self, header, projection):
        pass


class IdleBeam(AbstractBeam):

    def __init__(self):
        AbstractBeam.__init__(self)

    def convolve(self, img, boundary="zero"):
        return img

    def build_beam():
        return np.array([[1,],])


class GaussianBeam(AbstractBeam):

    def __init__(self, bmaj, bmin, bpa=0):
        ''' bmaj, bmin in pixel, bpa in radians'''
        self.bmin = bmin
        self.bmaj = bmaj
        self.bpa = bpa
        AbstractBeam.__init__(self)

    def __str__(self):
        return "GaussianBeam:X:%s,Y:%s,A:%s" % (self.bmaj, self.bmin, self.bpa)

    def build_beam(self):
        sigmax = nputils.gaussian_fwhm_to_sigma(self.bmaj)
        sigmay = nputils.gaussian_fwhm_to_sigma(self.bmin)
        support_x = nputils.get_next_odd(nputils.gaussian_support(sigmax))
        support_y = nputils.get_next_odd(nputils.gaussian_support(sigmay))
        support = max(support_x, support_y)
        width = [self.bmaj, self.bmin]
        # if beam is separable, go for the faster computation
        if self.bpa != 0 and self.bmaj != self.bmin:
            beam = gaussian(support, width=width, angle=self.bpa)
            beam = beam / beam.sum()
        elif self.bmaj != self.bmin:
            beam = (signalutils.gaussian(support_x, width=self.bmaj), 
                    signalutils.gaussian(support_y, width=self.bmin))
            beam = (beam[0] / beam[0].sum(), beam[1] / beam[1].sum())
        else:
            beam = signalutils.gaussian(support, width=self.bmaj)
            beam = beam / beam.sum()
        return beam

    def set_header(self, header, projection=None):
        if projection:
            scale = projection.mean_pixel_scale()
        else:
            scale = 1
        header.set("BMIN", self.bmin * scale)
        header.set("BMAJ", self.bmaj * scale)
        header.set("BPA", np.degrees(self.bpa))


class Transform(object):

    def __init__(self, fct_s2p, fct_p2s):
        self.fct_s2p = fct_s2p
        self.fct_p2s = fct_p2s

    def _transform(self, fct, xy):
        xy = np.asanyarray(xy)
        res = fct(np.atleast_2d(xy))
        # print "->", res
        if xy.ndim == 1:
            return res[0]
        return res

    def s2p(self, xy):
        res = self._transform(self.fct_s2p, xy)
        return res

    def p2s(self, xy):
        res = self._transform(self.fct_p2s, xy)
        return res

    def pixel_scales(self):
        raise NotImplementedError()


class IdentityTransform(Transform):

    def __init__(self):
        idle = lambda x: x
        Transform.__init__(self, idle, idle)

    def pixel_scales(self):
        return [1, 1]


class CompositeTransform(Transform):

    def __init__(self, child1, child2):
        self.child1 = child1
        self.child2 = child2
        s2p = lambda xy: child2.s2p(child1.s2p(xy))
        p2s = lambda xy: child1.p2s(child2.p2s(xy))
        Transform.__init__(self, s2p, p2s)

    def __str__(self):
        return "Ctr(%s, %s)" % (self.child1, self.child2)

    def pixel_scales(self):
        return self.child1.pixel_scales() * self.child2.pixel_scales()


class RotationTransform(Transform):

    def __init__(self, teta, center):
        ''' teta in radian'''
        self.center = center
        self.rotation_matrix = np.array([[np.cos(teta), np.sin(teta)], [-np.sin(teta), np.cos(teta)]])
        s2p = lambda xy: center + np.dot(xy - center, self.rotation_matrix.T)
        p2s = lambda xy: center + np.dot(xy - center, self.rotation_matrix)
        Transform.__init__(self, s2p, p2s)


class WCSTransform(Transform):

    def __init__(self, wcs):
        self.wcs = wcs
        s2p = lambda xy: self.wcs.wcs_world2pix(xy, 0)
        p2s = lambda xy: self.wcs.all_pix2world(xy, 0)
        Transform.__init__(self, s2p, p2s)

    def __str__(self):
        return "WCSTr()"

    def pixel_scales(self):
        cdelt = np.matrix(self.wcs.wcs.get_cdelt())
        pc = np.matrix(self.wcs.wcs.get_pc())
        return np.array(cdelt * pc)[0]


class ScaleTransform(Transform):

    def __init__(self, a, b, longitude_correction=1):
        ''' (x, y) * a * [longitude_correction, 1] + b '''
        self.a = np.array(a, dtype=np.float)
        self.b = np.array(b, dtype=np.float)
        self.lc = np.array([longitude_correction, 1])
        s2p = lambda xy: a * self.lc * xy + b
        p2s = lambda xy: (xy - b) / (a * self.lc)
        Transform.__init__(self, s2p, p2s)

    def __str__(self):
        return "ScaleTr(%s, %s)" % (self.a, self.b)

    def pixel_scales(self):
        return 1 / self.a


class ProjectionSettings(object):

    def __init__(self, unit=u.deg, relative=False, center='pix_ref', distance=None, z=None, cosmo=None):
        if z is not None:
            if cosmo is None:
                cosmo = cosmology.WMAP9
            dA = cosmo.angular_diameter_distance(z)
            distance = dA / (2 * np.tan(0.5))

        self.unit = unit
        self.relative = relative
        self.center = center
        self.distance = distance


class AbstractCoordinateSystem(object):

    def get_projection(self, settings):
        pass


class PixelCoordinateSystem(object):

    def __init__(self, shape=None, pix_ref=None, equ_unit=u.mas):
        self.shape = shape
        self.pix_ref = pix_ref
        self.equ_unit = equ_unit

    def get_equ_unit(self):
        return self.equ_unit

    def get_projection(self, settings):
        if settings.relative:
            if settings.center == 'center':
                if self.shape is not None:
                    center = p2i(np.array(self.shape)) / 2
                else:
                    print "Warning: Relative projection without image shape defined"
            elif settings.center == 'pix_ref':
                if self.pix_ref is not None:
                    center = self.pix_ref
                else:
                    print "Warning: Relative projection without pix ref defined"
            else:
                center = settings.center
            return RelativePixelProjection(self, center)
        return PixelProjection(self)

    def get_header(self):
        wcs = pywcs.WCS(naxis=2)

        scale = self.equ_unit.to(u.deg)

        wcs.wcs.crpix = np.array(self.pix_ref) + np.array([1, 1])
        wcs.wcs.crval = [0, 0]
        wcs.wcs.cdelt = [scale, scale]
        wcs.wcs.ctype = ['X', 'Y']

        return WorldCoordinateSystem(wcs, shape=self.shape), wcs.to_header()


class WorldCoordinateSystem(object):

    def __init__(self, wcs, shape=None):
        self.wcs = copy.deepcopy(wcs)
        self.shape = shape
        self._key = (tuple(self.wcs.wcs.crpix), tuple(self.wcs.wcs.crval), 
                     tuple(self.wcs.wcs.get_cdelt().flatten()), 
                     tuple(self.wcs.wcs.get_pc().flatten()), self.shape)

    def __eq__(x, y):
        return x._key == y._key

    def __hash__(self):
        return hash(self._key)

    def get_projection(self, settings):
        if settings.relative is True:
            assert self.shape is not None

            if settings.center == 'pix_ref':
                # crpix is with origin 1:
                center = np.array(self.wcs.wcs.crpix) - [1, 1]
            elif settings.center == 'center':
                center = np.array(self.shape)[::-1] / 2
            else:
                center = settings.center
            projection = RelativeWCSProjection(self, center, settings.unit, distance=settings.distance)
        else:
            projection = WCSProjection(self, unit=settings.unit, distance=settings.distance)
        return projection

    def get_header(self):
        return self, self.wcs.to_header()

    @staticmethod
    def new(self, xlabel, ylabel, pix_ref=[0, 0], cdelt=[1, 1], crval=[0, 0]):
        wcs = pywcs.WCS(naxis=2)

        # crpix is with origin 1:
        wcs.wcs.crpix = np.array(pix_ref) + np.array([1, 1])
        wcs.wcs.crval = [0, 0]
        wcs.wcs.cdelt = [1, 1]
        wcs.wcs.ctype = [xlabel, ylabel]

        return WorldCoordinateSystem(wcs)


class Projection(object):

    def __init__(self, transform, xlabel, ylabel, unit, coordinate_system):
        self.transform = transform
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.unit = unit
        self.coordinate_system = coordinate_system

    def __str__(self):
        return "Projection(%s, %s, %s, %s)" % (self.transform, self.xlabel, self.ylabel, self.unit)

    def get_xlabel(self):
        return "%s (%s)" % (self.xlabel, self.unit.name)

    def get_ylabel(self):
        return "%s (%s)" % (self.ylabel, self.unit.name)

    def get_unit(self):
        return self.unit

    def get_coordinate_system(self):
        return self.coordinate_system

    def _unit_tr(self, value, unit):
        if unit is None:
            return value
        return value * self.unit.to(unit)

    def p2s(self, xy_pixel, unit=None):
        ''' Accept 1D (x,y) or 2D N x 2 array '''
        return self._unit_tr(self.transform.p2s(xy_pixel), unit)

    def s2p(self, xy_coord, unit=None):
        ''' Accept 1D (x,y) or 2D N x 2 array '''
        return self._unit_tr(self.transform.s2p(xy_coord), unit)

    def pixel_scales(self, unit=None):
        return self._unit_tr(np.array(self.transform.pixel_scales()), unit)

    def mean_pixel_scale(self, unit=None):
        return self._unit_tr(0.5 * np.abs(self.pixel_scales()).sum(), unit)

    def angular_separation(self, xy_pixel1, xy_pixel2):
        xy_coord1 = self.p2s(xy_pixel1)
        xy_coord2 = self.p2s(xy_pixel2)
        return nputils.l2norm((xy_coord2 - xy_coord1)) * self.unit
    
    def angular_separation_pa(self, xy_pixel1, xy_pixel2):
        xy_coord1 = self.p2s(xy_pixel1)
        xy_coord2 = self.p2s(xy_pixel2)
        r, theta = nputils.coord_xy_to_rtheta(*np.array(xy_coord2 - xy_coord1).T)
        return r * self.unit, theta * u.radian

    def __get_delta_time(self, time):
        if isinstance(time, datetime.timedelta):
            time = time.total_seconds() * u.second
        if isinstance(time, TimeDelta):
            time = time.to(u.second)
        return time.decompose()
        
    def angular_velocity(self, xy_pixel1, xy_pixel2, time):
        d = self.angular_separation(xy_pixel1, xy_pixel2)
        return d.decompose() / self.__get_delta_time(time)

    def angular_velocity_vector(self, xy_pixel1, xy_pixel2, time):
        r, theta = self.angular_separation_pa(xy_pixel1, xy_pixel2)
        x, y = nputils.coord_rtheta_to_xy(r.value, theta.to(u.radian).value)
        d = np.array([x, y]) * r.unit
        return (d.decompose() / self.__get_delta_time(time)).T

    def proper_distance(self, xy_pixel1, xy_pixel2):
        return self.angular_separation(xy_pixel1, xy_pixel2)

    def proper_distance_pa(self, xy_pixel1, xy_pixel2):
        return self.angular_separation_pa(xy_pixel1, xy_pixel2)

    def proper_velocity(self, xy_pixel1, xy_pixel2, time, vector=False):
        d = self.proper_distance(xy_pixel1, xy_pixel2)
        return d.decompose() / self.__get_delta_time(time)

    def proper_velocity_vector(self, xy_pixel1, xy_pixel2, time):
        r, theta = self.proper_distance_pa(xy_pixel1, xy_pixel2)
        x, y = nputils.coord_rtheta_to_xy(r, theta)
        d = np.array([x.value, y.value]) * x.unit
        return (d.decompose() / self.__get_delta_time(time)).T

    def get_gh(self, locator=None, formatter=None):
        if formatter is None:
            # useMathText is a memory killer (https://github.com/matplotlib/matplotlib/issues/3177)
            formatter = FormatterPrettyPrint(useMathText=False)

        def transform_xy(x, y):
            return self.transform.s2p(np.array(np.atleast_1d(x, y)).T).T

        def inv_transform_xy(x, y):
            return self.transform.p2s(np.array(np.atleast_1d(x, y)).T).T

        return GridHelperCurveLinear((transform_xy, inv_transform_xy),
                                     grid_locator1=locator,
                                     grid_locator2=locator,
                                     tick_formatter1=formatter,
                                     tick_formatter2=formatter)

    def new_rotated_floating_axis(self, point, teta, nth_coord, value, axes, axis_direction="top"):
        rot_trans = RotationTransform(teta, point)
        transform = CompositeTransform(rot_trans, self.transform)
        rmatrix = np.array([[np.cos(teta), np.sin(teta)], [-np.sin(teta), np.cos(teta)]])

        def transform_xy(x, y):
            return transform.s2p(np.array(np.atleast_1d(x, y)).T).T

        def inv_transform_xy(x, y):
            return transform.p2s(np.array(np.atleast_1d(x, y)).T).T

        gh = GridHelperCurveLinear((transform_xy, inv_transform_xy))

        axis = gh.new_floating_axis(nth_coord, value, axis_direction=axis_direction, axes=axes)
        axes.axis["rotated:%s, %s" % (point, teta)] = axis

        return axis

    def set_transform(self, transform):
        self.transform.set(transform)


class AbstractRelativeProjection(Projection):

    def dfc(self, xy_pixel, unit=None):
        xy_coord = self.p2s(xy_pixel)
        return self._unit_tr(nputils.l2norm(xy_coord), unit)

    def direction(self, xy_pixel, unit=None):
        xy_coord = self.p2s(xy_pixel)
        return self._unit_tr(xy_coord / np.linalg.norm(xy_coord), unit)

    def pa(self, xy_pixel, unit=None):
        xy_coord = self.p2s(xy_pixel)
        x, y = xy_coord.T
        return self._unit_tr(np.arctan2(x, y), unit)


class WCSProjection(Projection):

    def __init__(self, coordinate_system, distance=None, unit=u.deg):
        ''' It make a copy of wcs in case image is transformed afterwards. Projection is valid at the time
            it is created. If you make transform to your image, this projection is invalid for the 
            transformed image. '''
        self.wcs = coordinate_system.wcs
        self.unit = unit
        self.distance = distance
        self.wcs_transform = WCSTransform(self.wcs)
        xlabel = self.wcs.wcs.ctype[0].split('-')[0]
        ylabel = self.wcs.wcs.ctype[1].split('-')[0]
        Projection.__init__(self, self.build_transform(), xlabel, ylabel, unit, coordinate_system)

    def get_cdelt_rota(self):
        cdelt = self.wcs.wcs.get_cdelt()
        pc = self.wcs.wcs.get_pc()
        cd = np.tile(cdelt, [2, 1]) * pc

        if cd[1, 0] > 0:
            rho_a = np.arctan2(cd[1, 0], cd[0, 0])
        elif cd[1, 0] < 0:
            rho_a = np.arctan2(-cd[1, 0], -cd[0, 0])
        else:
            rho_a = 0

        if cd[0, 1] > 0:
            rho_b = np.arctan2(cd[0, 1], -cd[1, 1])
        elif cd[0, 1] < 0:
            rho_b = np.arctan2(-cd[0, 1], cd[1, 1])
        else:
            rho_b = 0
        roll_angle = (rho_a + rho_b) / 2
        cdelt = np.array([cd[0, 0], cd[1, 1]])

        if cd[0, 0] != 0:
            cdelt[0] = cd[0, 0] / np.cos(roll_angle)
        else:
            cdelt[0] = cd[1, 0] / np.sin(roll_angle)

        if cd[1, 1] != 0:
            cdelt[1] = cd[1, 1] / np.cos(roll_angle)
        else:
            cdelt[1] = -cd[0, 1] / np.sin(roll_angle)

        return roll_angle, cdelt

    def build_transform(self):
        return WCSTransform(self.wcs)

    def absolute(self, xy_pix):
        from astropy.coordinates import SkyCoord

        ra, dec = self.wcs_transform.p2s(xy_pix).T
        return SkyCoord(ra * u.deg, dec * u.deg, distance=self.distance, frame='icrs')

    def angular_separation(self, xy_pixel1, xy_pixel2):
        return self.angular_separation_pa(xy_pixel1, xy_pixel2)[0]

    def angular_separation_pa(self, xy_pixel1, xy_pixel2):
        p1 = self.absolute(xy_pixel1)
        p2 = self.absolute(xy_pixel2)
        return p1.separation(p2).to(self.unit), p1.position_angle(p2)

    def proper_distance(self, xy_pixel1, xy_pixel2):
        if self.distance is None:
            return self.angular_separation(xy_pixel1, xy_pixel2)
            
        p1 = self.absolute(xy_pixel1)
        p2 = self.absolute(xy_pixel2)
        return p1.separation_3d(p2)

    def proper_distance_pa(self, xy_pixel1, xy_pixel2):
        if self.distance is None:
            return self.angular_separation_pa(xy_pixel1, xy_pixel2)

        p1 = self.absolute(xy_pixel1)
        p2 = self.absolute(xy_pixel2)
        return p1.separation_3d(p2), p1.position_angle(p2)

    def update(self):
        ''' Update due to wcs change '''
        self.set_transform(self.build_transform())

    def get_header(self):
        return self.wcs.to_header()


class RelativeWCSProjection(AbstractRelativeProjection, WCSProjection):

    def __init__(self, coordinate_system, xy_pixel_center, unit=u.deg, distance=None):
        self.xy_pixel_center = xy_pixel_center
        WCSProjection.__init__(self, coordinate_system, distance, unit)
        self.xlabel = "Relative " + self.xlabel
        self.ylabel = "Relative " + self.ylabel

    def build_transform(self):
        ra, dec = self.wcs_transform.p2s(self.xy_pixel_center)
        scale = 1 / float((u.deg).to(self.unit))
        scale_translation = ScaleTransform(scale, np.array([ra, dec]), 1 / np.cos(np.radians(dec)))
        return CompositeTransform(scale_translation, self.wcs_transform)


class PixelProjection(Projection):

    def __init__(self, coordinate_system=None):
        if coordinate_system is None:
            coordinate_system = PixelCoordinateSystem()
        unit = coordinate_system.get_equ_unit()
        Projection.__init__(self, IdentityTransform(), "X", "Y", unit, coordinate_system)


class RelativePixelProjection(AbstractRelativeProjection, Projection):

    def __init__(self, coordinate_system, xy_pixel_center):
        unit = coordinate_system.get_equ_unit()
        Projection.__init__(self, ScaleTransform(1, np.array(xy_pixel_center), 1), "X", "Y", unit, coordinate_system)


class ImageSet(object):
    ''' Transitional object used to store beam information 
        until we can save full detection result'''

    def __init__(self):
        self.images = dict()

    def merge(self, other):
        self.images.update(other.images)

    def add(self, epoch, filename, beam):
        self.images[epoch] = (filename, beam)

    def add_img(self, img):
        epoch = img.get_epoch()
        beam = img.get_beam()
        filename = "image"
        if isinstance(img, FitsImage) or isinstance(img, PilImage):
            filename = img.get_filename()
        assert epoch not in self.images
        self.add(epoch, filename, beam)

    def get_filename(self, epoch):
        return self.images[epoch][0]

    def get_beam(self, epoch):
        return self.images[epoch][1]

    def get_epochs(self):
        return sorted(self.images.keys())

    def to_file(self, filename, projection):
        '''Format is: filename, epoch, bmaj, bmin, bpa'''
        array = []
        scale = projection.mean_pixel_scale()
        for epoch, (img_filename, beam) in nputils.get_items_sorted_by_keys(self.images):
            epoch = float(nputils.datetime_to_epoch(epoch))
            if isinstance(beam, GaussianBeam):
                beam_data = [beam.bmaj * scale, beam.bmin * scale, beam.bpa]
            else:
                beam_data = [0, 0, 0]
            array.append([img_filename, str(epoch)] + beam_data)
        np.savetxt(filename, np.array(array, dtype=object), fmt=["%s", "%s", "%.5f", "%.5f", "%.5f"])
        print "Saved image set @ %s" % filename

    @staticmethod
    def from_file(filename, projection):
        new = ImageSet()
        array = np.loadtxt(filename, dtype=str)
        scale = projection.mean_pixel_scale()
        for file, epoch, bmaj, bmin, bpa in array:
            epoch = nputils.epoch_to_datetime(float(epoch))
            if bmaj != 0:
                beam = GaussianBeam(float(bmaj) / scale, float(bmin) / scale, float(bpa))
            else:
                beam = IdleBeam()
            new.add(epoch, file, beam)

        print "Loaded image set from %s" % filename
        return new


class ImageMeta(object):

    def __init__(self, epoch, coordinate_system, beam):
        self.epoch = epoch
        self.coordinate_system = coordinate_system
        self.beam = beam

    def get_coordinate_system(self):
        return self.coordinate_system

    def get_beam(self):
        return self.beam

    def get_epoch(self):
        return self.epoch


class Image(object):

    EPOCH_COUNTER = 0

    def __init__(self, data, epoch=None, beam=None, pix_ref=None):
        self.data = data
        if beam is None:
            beam = IdleBeam()
        self.beam = beam
        if pix_ref is None:
            pix_ref = np.array(self.data.shape)[::-1] / 2
        self.pix_ref = pix_ref
        if epoch is None:
            self.epoch = Image.EPOCH_COUNTER
            Image.EPOCH_COUNTER += 1
        else:
            self.epoch = epoch
        if self.beam is None:
            self.beam = IdleBeam()

    def __add__(self, other):
        if isinstance(other, Image):
            other = other.get_data()
        new = self.copy()
        new.get_data() + other
        return new

    def __sub__(self, other):
        if isinstance(other, Image):
            other = other.get_data()
        new = self.copy()
        new.get_data() - other
        return new

    def __mul__(self, other):
        if isinstance(other, Image):
            other = other.get_data()
        new = self.copy()
        new.get_data() * other
        return new

    def __div__(self, other):
        if isinstance(other, Image):
            other = other.get_data()
        new = self.copy()
        new.get_data() / other
        return new

    def get_meta(self):
        return ImageMeta(self.get_epoch(), self.get_coordinate_system(), self.get_beam())

    def get_coordinate_system(self):
        return PixelCoordinateSystem(self.data.shape, self.pix_ref)

    def get_projection(self, *args, **kargs):
        if len(args) == 1 and isinstance(args[0], ProjectionSettings):
            settings = args[0]
        else:
            settings = ProjectionSettings(*args, **kargs)
        return self.get_coordinate_system().get_projection(settings)

    def has_beam(self):
        return self.get_beam() is not None

    def get_beam(self):
        return self.beam

    def get_pix_ref(self):
        return self.pix_ref

    def set_pix_ref(self, pix_ref):
        self.pix_ref = pix_ref

    def get_title(self):
        return ""

    def get_epoch(self):
        return self.epoch

    def get_region(self, center, shape, projection=None):
        ''' Return an ImageRegion '''
        if projection is not None:
            center = projection.s2p(center)
        img = self.get_data()
        array, index = nputils.zoom(img, np.array(center), shape, pad=False, output_index=True)
        return ImageRegion(img, index)

    def resize(self, shape):
        self.data, padding_index, array_index = nputils.resize(self.data, shape, output_index=True)
        def i(n):
            if n is None:
                return 0
            return n
        shift = [i(array_index[0]) - i(padding_index[0]), i(array_index[1]) - i(padding_index[1])]
        self.set_pix_ref(np.round(self.get_pix_ref() - shift))
        return shift

    # def partition(self, bx, by, ox=0, oy=0):
    #     img = self.get_data()
    #     for x in range(0, img.shape[0] - ox, bx - ox):
    #         for y in range(0, img.shape[0] - oy, by - oy):
    #             yield ImageRegion(img, (x, y, min(x + bx, img.shape[0]), min(y + by, img.shape[1])))

    def crop(self, xy_p1, xy_p2, projection=None):
        ''' xy_p1 and xy_p2 as pix, except if projection is provided '''
        if projection is not None:
            xy_p1, xy_p2 = np.round(projection.s2p([xy_p1, xy_p2])).astype(int)
        ex = [0, self.data.shape[1]]
        ey = [0, self.data.shape[0]]
        xlim1, xlim2 = sorted([nputils.clamp(xy_p1[0], *ex), nputils.clamp(xy_p2[0], *ex)])
        ylim1, ylim2 = sorted([nputils.clamp(xy_p1[1], *ey), nputils.clamp(xy_p2[1], *ey)])
        print xlim1, xlim2, ylim1, ylim2
        self.data = self.data[ylim1:ylim2, xlim1:xlim2].copy()
        xy_p1 = np.array([xlim1, ylim1])
        xy_p2 = np.array([xlim2, ylim2])
        self.set_pix_ref(np.round(self.get_pix_ref() - xy_p1))
        return xy_p1, xy_p2

    def shift(self, delta, projection=None):
        ''' delta as xy_pix, except if projection is provided '''
        if projection is not None:
            delta = delta / projection.pixel_scales()
        print "Shift:", delta
        self.data = nputils.shift2d(self.data, np.round(p2i(delta)))

    def rotate(self, angle_rad, spline_order=0, smooth_len=3):
        self.data = rotate(self.data, - angle_rad / (2 * np.pi) * 360, reshape=False, order=spline_order)

        if smooth_len > 0:
            self.data = nputils.smooth(self.data, smooth_len, mode='same' )

        rmatrix = np.array([[np.cos(angle_rad), np.sin(angle_rad)], [-np.sin(angle_rad), np.cos(angle_rad)]])
        center = p2i(np.array(self.data.shape) / 2.)
        self.set_pix_ref(center + np.dot(self.get_pix_ref() - center, rmatrix))

        return rmatrix

    def zoom(self, factor, order=3, mode='constant', cval=0):
        self.data = zoom(self.data, factor, order=order, mode=mode, cval=cval)

        self.set_pix_ref(factor * self.get_pix_ref())

    @staticmethod
    def from_image(image, data=None):
        ''' Return a copy of image with new data set to zeros or to an optional data'''
        new = image.copy()
        if data is None:
            data = np.zeros_like(image.data)
        new.set_data(data)
        return new

    def copy(self, full=False):
        new = copy.copy(self)
        if full:
            new.data = self.data.copy()
        return new

    def set_data(self, data):
        self.data = data

    def get_data(self):
        return self.data

    def build_hdu(self):
        hdu = pyfits.PrimaryHDU(self.data)
        wcs_coord_sys, header = self.get_coordinate_system().get_header()
        hdu.header.update(header)
        self.get_beam().set_header(hdu.header, wcs_coord_sys.get_projection(ProjectionSettings()))
        if isinstance(self.get_epoch(), datetime.date):
            epoch = self.get_epoch().strftime("%Y-%m-%d")
            hdu.header.set('DATE-OBS', epoch)

        return hdu

    def save_to_fits(self, filename):
        hdu = self.build_hdu()
        hdulist = pyfits.HDUList([hdu])
        hdulist.writeto(filename, clobber=True)


class PilImage(Image):

    def __init__(self, file):
        self.file = file
        self.pil_image = PIL.Image.open(file)
        Image.__init__(self, np.array(self.pil_image, dtype=np.float64))

    def get_filename(self):
        return self.file


class FitsImage(Image):

    GENERIC_HEADER_KEYS = ['TELESCOP', 'INTRUME', 'OBSERVER', 'OBJECT']

    def __init__(self, file, freq_key="CRVAL3", float64=True, extension=0):
        try:
            fits = pyfits.open(file)
        except Exception, e:
            print "Issue reading", file
            raise e
        self.freq_key = freq_key
        self.beam = None
        self.header = fits[extension].header
        self.zero_header = fits[0].header
        self.file = file

        if self.header['NAXIS'] == 4:
            data = fits[extension].data[0, 0]
        elif self.header['NAXIS'] == 2:
            data = fits[extension].data
        else:
            raise ValueError("Not supported: naxis %s" % self.header['NAXIS'])
        if float64:
            data = data.astype(np.float64)

        self.wcs = pywcs.WCS(self.header, naxis=2, fobj=fits)
        if "DATE-OBS" in self.zero_header:
            epoch = nputils.guess_date(self.zero_header["DATE-OBS"], ["%Y-%m-%d", "%d/%m/%y"])
        else:
            epoch = None

        self.beam_data = None
        if 'BMAJ' in self.header:
            self.beam_data = [self.header['BMAJ'], self.header['BMIN'],self.header['BPA']]
        elif 'HISTORY' in self.header:
            self.beam_data = self.check_aips_clean_beam()

        fits.close()

        Image.__init__(self, data, epoch=epoch, beam=None, pix_ref=None)

    def __str__(self):
        return "FitsImage(%s)" % self.file

    def get_filename(self):
        return self.file

    def set_crval(self, crval):
        self.wcs.wcs.crval = crval
        self.wcs.wcs.set()

    def set_crpix(self, crpix):
        self.wcs.wcs.crpix = crpix
        self.wcs.wcs.set()

    def get_pix_ref(self):
        # crpix is with origin 1, pix_ref with origin 0
        return np.array(self.wcs.wcs.crpix) - [1, 1]

    def set_pix_ref(self, pix_ref):
        # crpix is with origin 1:
        self.set_crpix(np.array(pix_ref) + [1, 1])

    def get_beam(self):
        if self.beam_data is None:
            return IdleBeam()
        bmaj, bmin, bpa = self.beam_data
        scale = self.get_projection().mean_pixel_scale()
        if bmaj < scale:
            #Warning: Pixel increment seams wrong (milli degree ? we will assume so)"
            scale = scale * 1 / 1000.
        return GaussianBeam(bmaj / scale, bmin / scale, np.radians(bpa))

    def check_aips_clean_beam(self):
        pattern = 'AIPS\s*CLEAN\s*BMAJ=(.*)BMIN=(.*)BPA=(.*)'
        for line in self.header['HISTORY']:
            res = re.search(pattern, line)
            if res is not None:
                bmaj, bmin, bpa = [float(k) for k in res.group(1, 2, 3)]
                self.header['BMAJ'] = bmaj
                self.header['BMIN'] = bmin
                self.header['BPA'] = bpa
                return [bmaj, bmin, bpa]
        return None

    def rotate(self, angle_rad, spline_order=5, smooth_len=3):
        rmatrix = Image.rotate(self, angle_rad, spline_order, smooth_len)

        new_pc = np.dot(self.wcs.wcs.get_pc(), rmatrix)
        self.wcs.wcs.pc = new_pc

        if self.beam_data is not None:
            self.beam_data[2] += np.degrees(angle_rad)

        self.wcs.wcs.set()

        return rmatrix

    def zoom(self, factor, order=3, mode='constant', cval=0):
        Image.zoom(self, factor, order=order, mode=mode, cval=cval)

        self.wcs.wcs.cdelt = self.wcs.wcs.cdelt / float(factor)

        self.wcs.wcs.set()

    def get_coordinate_system(self):
        return WorldCoordinateSystem(self.wcs, self.data.shape)

    def get_coord(self, xy_pix, distance=None):
        projection = WCSProjection(WorldCoordinateSystem(self.wcs))
        ra, dec = projection.p2s(xy_pix)
        return ICRS(ra, dec, unit=(u.degree, u.degree), distance=distance)

    def get_title(self):
        title = []
        if self.get_object() is not None:
            title.append(self.get_object())
        if self.get_telescop() is not None:
            title.append(self.get_telescop().strip())
        if self.get_frequency() is not None and self.get_frequency() > 0:
            frequency = nputils.display_measure(self.get_frequency(), "Hz")
            title.append("at %s" % frequency)
        if self.get_epoch() is not None:
            title.append("Epoch: %s" % self.get_epoch())
        return ', '.join(title)

    def get_unit(self):
        return self.header.get("BUNIT")

    def get_object(self):
        return self.header.get("OBJECT", "")

    def get_telescop(self):
        return self.header.get("TELESCOP", None)

    def get_frequency(self):
        return self.header.get(self.freq_key, None)

    def copy(self, full=False):
        new = Image.copy(self, full=full)
        new.wcs = copy.deepcopy(self.wcs)
        return new

    def build_hdu(self):
        hdu = Image.build_hdu(self)
        # hdu.header.update(self.wcs.to_header())
        for key in self.GENERIC_HEADER_KEYS:
            if key in self.header:
                hdu.header[key] = self.header[key]
        return hdu

    @staticmethod
    def new(data, beam, coord_sys, epoch=None):
        pass


class StackedImage(FitsImage):

    def __init__(self, fits_image):
        self.first = fits_image
        if isinstance(fits_image, FitsImage):
            self.freq_key = fits_image.freq_key
            self.beam_data = fits_image.beam_data
            self.header = fits_image.header.copy()
            self.wcs = fits_image.wcs.copy()
        self.epoch = fits_image.get_epoch()
        self.data = fits_image.data.copy()
        self.all_datas = []

        self.epochs = [fits_image.get_epoch()]

    def __len__(self):
        return len(self.epochs)

    @staticmethod
    def from_file(file):
        img = StackedImage(FitsImage(file))
        img.epochs = []
        if 'STAN' in img.header:
            for i in range(img.header['STAN']):
                img.epochs.append(nputils.guess_date(img.header['STA%i' % (i + 1)], ["%Y-%m-%d", "%d/%m/%y"]))
        else:
            img.epochs = [img.get_epoch()]

        return img

    @staticmethod
    def from_imgs(imgs):
        mgr = StackedImageManager()
        for img in imgs:
            mgr.add(img)
        return mgr.get()

    def add(self, image, action='mean'):
        self.all_datas.append(image.data)
        if not nputils.shape_eq(image.data, self.data):
            raise Exception("Image shape are not adequate for stacking")
        if action is 'mean':
            self.data = self.data * (len(self) / float(len(self) + 1)) + image.data / float(len(self) + 1)
        elif action is 'add':
            self.data += image.data
        elif action is 'max':
            self.data = np.max([self.data, image.data], axis=0)
        elif action is 'min':
            self.data = np.min([self.data, image.data], axis=0)
        elif action.startswith('per'):
            self.data = np.percentile(self.all_datas, int(action[3:]), axis=0)
        elif action is 'median':
            self.data = np.median(self.all_datas, axis=0)
        if isinstance(image, StackedImage):
            self.epochs = list(set(self.epochs) | set(image.epochs))
        else:
            self.epochs.append(image.get_epoch())

    def get_epochs(self):
        return sorted(self.epochs)

    def get_coordinate_system(self):
        return self.first.get_coordinate_system()

    def get_beam(self):
        return self.first.get_beam()

    def get_title(self):
        title = self.get_object()
        if self.get_telescop() is not None and self.get_telescop().strip():
            title += ", %s" % self.get_telescop().strip()
        if self.get_frequency() is not None:
            frequency = nputils.display_measure(self.get_frequency(), "Hz")
            title += " at %s" % frequency
        epochs = self.get_epochs()
        title += "\nStacked images: %s epochs from %s to %s" % (len(epochs), epochs[0], epochs[-1])
        return title

    def build_hdu(self):
        if isinstance(self.first, FitsImage):
            hdu = FitsImage.build_hdu(self)
            hdu.header['STAN'] = len(self)

            for i, epoch in enumerate(self.get_epochs()):
                hdu.header['STA%i' % (i + 1)] = epoch.strftime("%Y-%m-%d")
        else:
            hdu = Image.build_hdu(self)
        return hdu


class StackedImageManager():

    def __init__(self):
        self.image = None

    def __len__(self):
        if self.image is None:
            return 0
        return len(self.image)

    def add(self, image, action='mean'):
        if self.image is None:
            self.image = StackedImage(image)
        else:
            self.image.add(image, action=action)

    def get(self):
        return self.image


class FastHeaderReader(list):

    _RE_FITS_HEADER_LINE = re.compile("^([^=]{8})=([ ]*'.*'[ ]*|[ ]*[0-9.\-\+E]+[ ]*|[ ]*NAN[ ]*|[ ]*[TF][ ]*)/?(.*)$")

    def __init__(self, file, keys=None):

        self.file = file
        self.keys = keys
        self.read()

    def read(self):
        fd = open(self.file)
        for i in range(100):
            line = fd.read(80)
            if line == 'END' + ' ' * 77:
                break
            key = line[:8].rstrip()
            if self.keys and key not in self.keys:
                continue
            if key == 'COMMENT' or key == 'HISTORY':
                continue
            match = self._RE_FITS_HEADER_LINE.match(line)
            if match is None:
                continue
                # raise Exception("Error while parsing '%s' at line '%s'" % (self.file, line))
            (key, value, comment) = match.groups()
            value = value.strip()
            key = key.strip()
            if comment.strip() != '':
                comment = comment.rstrip()
            self.append({"key": key, "value": value, "comment": comment,
                         "offset": 80 * i, "newline": ''})
            if self.keys:
                self.keys.remove(key)
                if not self.keys:
                    break
        fd.close()

    def __get_line(self, key):
        for line in self:
            if key == line['key']:
                return line
        raise Exception("Pas de clef '%s' dans le header" % key)

    def __format_value(self, value):
        if value == 'T':
            return True
        elif value == 'F':
            return False
        elif value[0] == "'":
            value = value[1:-1].rstrip()
            if value == '':
                value = ' '
            return value
        return decimal.Decimal(value)

    def get_value(self, key):
        return self.__format_value(self.get_raw_value(key))

    def get_raw_value(self, key):
        return self.__get_line(key)['value']

    def get_comment(self, key):
        return self.__get_line(key)['comment'].lstrip()

    def get_keys(self):
        return [a['key'] for a in self]

    def has_key(self, key):
        return bool(key in self.get_keys())

    def get_items(self):
        return [(a['key'], self.__format_value(a['value'])) for a in self]


class Mask(Image):

    def __init__(self, mask):
        Image.__init__(self, mask)

    @staticmethod
    def from_mask_list(masks):
        return Mask(reduce(lambda x, y: x + y, [k.get_mask() for k in masks]).astype(bool))

    def intersection(self, other):
        self.data = self.data * other.data
        return self

    def union(self, other):
        self.data = (self.data + other.data).astype(bool)
        return self

    def difference(self, other):
        self.data = self.data * (- other.data.astype(bool))
        return self

    def get_mask(self):
        return self.data

    def get_area(self):
        return self.get_mask().sum()


class Region(object):
    ''' Wrapper for pyregion ShapeList, so that we can deal directly with CoordinateSystsem'''

    def __init__(self, filename):
        self.filename = filename
        self.region = pyregion.open(filename)
        self.pyregion_cache = nputils.LimitedSizeDict(size_limit=50)

    def __str__(self):
        return "Region(%s)" % os.path.basename(self.get_filename())

    def get_filename(self):
        return self.filename

    def get_pyregion(self, coordinate_system=None):
        if not coordinate_system in self.pyregion_cache:
            if isinstance(coordinate_system, WCSProjection) or isinstance(coordinate_system, WorldCoordinateSystem):
                region = self.region.as_imagecoord(coordinate_system.get_header()[1])
            else:
                region = self.region
            self.pyregion_cache[coordinate_system] = region
        return self.pyregion_cache[coordinate_system]

    def get_poly_region(self, coordinate_system):
        import poly_editor

        return poly_editor.PolyRegion.from_file(self.filename, coordinate_system)

    def get_name(self):
        ''' Assuming a single shape region '''
        pyregion = self.get_pyregion()
        return pyregion[0].attr[1].get("text", "")

    def get_color(self):
        ''' Assuming a single shape region '''
        import plotutils

        pyregion = self.get_pyregion()
        color = pyregion[0].attr[1].get("color", "blue")
        if hasattr( color):
            color = getattr(plotutils, color)
        return color


class ImageRegion(Image):

    ''' Represent a portion of an image'''

    def __init__(self, img, index, shift=None, copy=False):
        ''' img: the original image. No copy is made
            index: the region of interest
            shift: (optional)
            copy: if True, then the region of interest is copyed, allowing to free the original array (False by default)
         '''
        self.index = index
        # x0, y0, x1, y1 = index
        # if x0 < 0 or x1 > img.shape[0] or y0 < 0 or y1 > img.shape[1]:
        #     print img.shape, index
        #     raise Exception
        self.shape = img.shape
        self.img = img[nputils.index2slice(self.index)]
        if copy:
            self.img = self.img.copy()
        self.set_shift(shift)

    @staticmethod
    def from_list(regions):
        builder = ImageBuilder()
        for region in regions:
            builder.add(region)
        return builder.get()

    def set_shift(self, shift):
        ''' shift shall be of type int or will be rounded '''
        if shift is not None:
            self.shift = np.round(shift)
        else:
            self.shift = None

    def get_shift(self):
        if self.shift is None:
            return [0] * len(self.shape)
        return self.shift

    def check_shift(self, shift):
        for (x0, x1), sx, dx in zip(zip_index(self.index), self.shape, self.get_shift()):
            if x1 + dx <= 0 or x0 + dx >= sx:
                return False
        return True

    def get_shape(self):
        return self.shape

    def get_region(self):
        return self.img[self.get_region_slice()]

    def get_slice(self):
        return nputils.index2slice(self.get_index())

    def get_index(self):
        ia = []
        ib = []
        for (x0, x1), sx, dx in zip(zip_index(self.index), self.shape, self.get_shift()):
            ia.append(nputils.clamp(x0 + dx, 0, sx))
            ib.append(nputils.clamp(x1 + dx, 0, sx))
        return ia + ib

    def get_center(self):
        return np.array([x0 + (x1 - x0) / 2. for x0, x1 in zip_index(self.get_index())], dtype=np.int)

    def get_center_of_mass(self):
        # TODO: optimize
        return np.array(measurements.center_of_mass(self.get_data()))

    def get_coord_max(self):
        # TODO: optimize
        return np.array(nputils.coord_max(self.get_data()))

    def get_region_slice(self):
        slices = []
        for (x0, x1), sx, dx in zip(zip_index(self.index), self.shape, self.get_shift()):
            if x0 + dx < 0:
                slices.append(slice(-(x0 + dx), None))
            elif x1 + dx > sx:
                slices.append(slice(None, -((x1 + dx) - sx)))
            else:
                slices.append(slice(None, None))

        return slices

    def get_data(self):
        img = np.zeros(self.shape)
        img[self.get_slice()] += self.get_region()
        return img

    def extend(self, nx, ny):
        ia = []
        ib = []
        for (x0, x1), sx in zip(zip_index(self.index), self.shape,):
            ia.append(nputils.clamp(x0 - nx, 0, sx))
            ib.append(nputils.clamp(x1 + nx, 0, sx),)
        return ia + ib


class ImageBuilder(object):

    def __init__(self):
        self.img = None
        self.index = [1e10, 1e10, 0, 0]

    def add(self, region):
        if self.img is None:
            self.img = np.zeros(region.get_shape())
        img = region.get_region()
        try:
            self.img[region.get_slice()] += img
        except Exception:
            print img.shape, region.get_shape(), region.get_slice()
            raise Exception
        a = self.index
        b = region.get_index()
        self.index = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]

    def get(self):
        return ImageRegion(self.img, self.index, copy=True)


def get_ensemble_index(img_regions):
    indexs = zip(*[k.get_index() for k in img_regions])
    return [min(k) for k in indexs[:len(indexs) / 2]] + [max(k) for k in indexs[len(indexs) / 2:]]


def zip_index(index):
    i = len(index) / 2
    return [(d0, d1) for d0, d1 in zip(index[:i], index[i:])]


def join_image_region(img_regions, target_shape, fill_mode='add'):
    ''' Experimental! '''
    out = np.zeros(target_shape)
    new_positions = [[] for k in img_regions]
    for dim, lout, (d0, d1) in zip(range(out.ndim), target_shape, zip_index(get_ensemble_index(img_regions))):
        a = float(lout) / (d1 - d0)
        for img_region, new_position in zip(img_regions, new_positions):
            p0, p1 = zip_index(img_region.index)[dim]
            if (d1 - d0) == (p1 - p0):
                a = 0
            else:
                a = (lout - (p1 - p0)) / float((d1 - d0) - (p1 - p0))
            # print "Longeur total:", (d1 - d0), "Longeur region:", (p1 - p0)
            # print "Dimension:", dim, ",", img_region.get_region().shape, (d1 - d0) - (p1 - p0), "vs", lout - (p1 - p0), "->", a
            # print "Position:", (p0, p1), (p0 - d0), "New pos:", a * (p0 - d0)
            new_position.append(np.round(a * (p0 - d0)))

    for img_region, new_position in zip(img_regions, new_positions):
        nputils.fill_at(out, new_position, img_region.get_region(), mode=fill_mode)

    com_out = measurements.center_of_mass(out)
    initial_regions = ImageRegion.from_list(img_regions)
    com_initial = initial_regions.get_center_of_mass()
    x0 = np.clip(np.round(com_initial - com_out), 0, initial_regions.get_shape())
    x1 = np.clip(x0 + np.array(target_shape) - 1, 0, initial_regions.get_shape())
    new_img = np.zeros(initial_regions.get_shape())
    nputils.fill_at(new_img, x0, out)

    return ImageRegion(new_img, tuple(x0) + tuple(x1))


def test_poly_editor():
    # fits = "/homes/fmertens/data/crab/H1-FL.FITS"
    fits = "/homes/fmertens/data/3c273/mojave/full_stack_image.fits"

    img = FitsImage(fits)

    create_poly_region(img)
    

def test_beam():
    import plotutils
    fits = "/homes/fmertens/data/m87/cwalker/full_stack_image.fits"

    img = FitsImage(fits)
    print img.get_beam()

    print img.get_beam()
    stack = plotutils.FigureStack()

    fig, ax = stack.add_subplots("test")
    plotutils.imshow_image(ax, img)

    stack.show()


def test_save_fits():
    import plotutils

    file = os.path.expanduser("~/test.fits")
    data = lena()
    beam = GaussianBeam(50, 20, np.radians(20))
    img = Image(data, pix_ref=[0, 0], epoch=datetime.date(2010, 01, 20), beam=beam)
    img.save_to_fits(file)

    rimg = FitsImage(file)

    stack = plotutils.FigureStack()

    fig, ax = stack.add_subplots("test")
    prj = img.get_projection(unit=u.mas)
    plotutils.imshow_image(ax, rimg, projection=prj)

    stack.show()


def test_image_region():
    from utils import imgutils, plotutils
    lena = imgutils.lena()[::-1]

    img = ImageRegion(lena, [110, 120, 260, 280])
    img.set_shift([25, 25])


    stack = plotutils.FigureStack()

    fig, ax = stack.add_subplots("test")
    ax.imshow(img.get_data())

    stack.show()


if __name__ == '__main__':
    # test_poly_editor()
    # test_beam()
    # test_save_fits()
    test_image_region()


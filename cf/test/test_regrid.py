import datetime
import faulthandler
import os
import unittest

faulthandler.enable()  # to debug seg faults and timeouts

import numpy as np

import cf

try:
    import ESMF
except Exception:
    ESMF_imported = False
else:
    ESMF_imported = True


methods = (
    "linear",
    "conservative",
    "conservative_2nd",
    "nearest_dtos",
    "nearest_stod",
    "patch",
)


def regrid_ESMF(coord_sys, method, src, dst, **kwargs):
    """Help function that regrids Field data using pure ESMF.

    Used to verify `cf.Field.regrids` nad `cf.Field.regridc`

    """
    ESMF_regrid = cf.regrid.regrid(
        coord_sys, src, dst, method, _return_regrid=True, **kwargs
    )

    if coord_sys == "spherical":
        src = src.transpose(["X", "Y", "T"]).squeeze()
        dst = dst.transpose(["X", "Y", "T"]).squeeze()
    else:
        pass
#    print("src.array=", src.array)

    src_field = ESMF.Field(ESMF_regrid.srcfield.grid, "src")
    dst_field = ESMF.Field(ESMF_regrid.dstfield.grid, "dst")

#    print (src_field.grid)
#    print (dst_field.grid)

    fill_value = 1e20
    src_field.data[...] = np.ma.MaskedArray(src.array, copy=False).filled(
        fill_value
    )
#    print("src_field.data[...]=", src_field.data[...])
    dst_field.data[...] = fill_value

    ESMF_regrid(src_field, dst_field, zero_region=ESMF.Region.SELECT)
#    print("dst_field.data[...]=", dst_field.data[...])

    return np.ma.MaskedArray(
        dst_field.data.copy(),
        mask=(dst_field.data[...] == fill_value),
    )


class RegridTest(unittest.TestCase):
    filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "regrid.nc"
    )

    @unittest.skipUnless(ESMF_imported, "Requires ESMF package.")
    def test_Field_regrids(self):
        self.assertFalse(cf.regrid_logging())

        dst, src0 = cf.read(self.filename)
        
        src0.transpose(["X", "Y", "T"], inplace=True)
        dst.transpose(["Y", "T", "X"], inplace=True)

        dst[2:25, :, 2:35] = np.ma.masked

        for use_dst_mask in (True, False, True):
            print ("use_dst_mask=", use_dst_mask)
            src = src0.copy()
            
            print("        UNMASKED SOURCE")
            # No source grid masked points
            for method in (
                    "linear",
                    "conservative",
                    "conservative_2nd",
#                    "nearest_dtos",
                    "nearest_stod",
                    "patch",
            ):

                print("\n", method)
                x = src.regrids(dst, method=method, use_dst_mask=use_dst_mask)
                x.transpose(['X', 'Y', 'T'], inplace=True)
                x = x.array
                for t in (0, 1):
                    print("t=", t)
                    y = regrid_ESMF("spherical", method,
                                    src.subspace(T=[t]), dst,
                                    use_dst_mask=use_dst_mask)
                    a = x[..., t]
                    print ((y - a).max())
                    print ('y=', y[:4])
                    print ('a=', a[:4])
                    print ('y-a=',(y - a)[:4])
                    self.assertTrue(np.allclose(y, a, atol=1e-12, rtol=0))
#                    if method == 'nearest_dtos':#
#                        print (1/0)
            # Mask the souce grid with the same mask over all regridding
            # slices
            src[slice(1, 9, 1), slice(1, 10, 1), :] = cf.masked
    
            print("        MASKED SOURCE (INVARIANT)")
            for method in methods:
                x = src.regrids(dst, method=method)
                x.transpose(["X", "Y", "T"], inplace=True)
                x = x.array
                for t in (0, 1):
                    print("t=", t)
                    y = regrid_ESMF("spherical", method, src.subspace(T=[t]), dst)
                    a = x[..., t]
    
                    if isinstance(a, np.ma.MaskedArray):
                        self.assertTrue((y.mask == a.mask).all())
                    else:
                        self.assertFalse(y.mask.any())
    
                    #                print((y - a).max())
                    #                print(a, y)
                    self.assertTrue(np.allclose(y, a, atol=1e-12, rtol=0))
    
            # Now make the source mask vary over different regridding
            # slices
            src[slice(11, 19, 1), slice(11, 20, 1), 1] = cf.masked
    
            print("        MASKED SOURCE (VARIABLE)")
            for method in (
                "linear",
                "conservative",
                "nearest_dtos",
            ):
                #            print("\n\n\n", method)
                x = src.regrids(dst, method=method)
                x.transpose(["X", "Y", "T"], inplace=True)
                x = x.array
                for t in (0, 1):
                    #                print("t=", t)
                    y = regrid_ESMF("spherical", method, src.subspace(T=[t]), dst)
                    a = x[..., t]
    
                    if isinstance(a, np.ma.MaskedArray):
                        self.assertTrue((y.mask == a.mask).all())
                    else:
                        self.assertFalse(y.mask.any())
    
                    self.assertTrue(np.allclose(y, a, atol=1e-12, rtol=0))
    
            # Can't compute the regrid of the following methods when the
            # source grid mask varies over different regridding slices
            for method in (
                "conservative_2nd",
                "nearest_stod",
                "patch",
            ):
                with self.assertRaises(ValueError):
                    src.regrids(dst, method=method).array


#

#    @unittest.skipUnless(cf._found_ESMF, "Requires ESMF package.")
#    def test_Field_regridc(self):
#        self.assertFalse(cf.regrid_logging())
#        with cf.atol(1e-11):
#            for chunksize in self.chunk_sizes:
#                self.assertFalse(cf.regrid_logging())
#                with cf.chunksize(chunksize):
#                    f1 = cf.read(self.filename7)[0]
#                    f2 = cf.read(self.filename8)[0]
#                    f3 = cf.read(self.filename9)[0]
#                    self.assertTrue(
#                        f3.equals(f1.regridc(f2, axes="T", method="linear")),
#                        f"destination=time series, CHUNKSIZE={chunksize}",
#                    )
#                    f4 = cf.read(self.filename1)[0]
#                    f5 = cf.read(self.filename2)[0]
#                    f6 = cf.read(self.filename10)[0]
#                    self.assertTrue(
#                        f6.equals(
#                            f4.regridc(
#                                f5, axes=("X", "Y"), method="conservative"
#                            )
#                        ),
#                        f"destination=global Field, CHUNKSIZE={chunksize}",
#                    )
#                    self.assertTrue(
#                        f6.equals(
#                            f4.regridc(
#                                f5, axes=("X", "Y"), method="conservative"
#                            )
#                        ),
#                        f"destination=global Field, CHUNKSIZE={chunksize}",
#                    )
#                    dst = {"X": f5.dim("X"), "Y": f5.dim("Y")}
#                    self.assertTrue(
#                        f6.equals(
#                            f4.regridc(
#                                dst, axes=("X", "Y"), method="conservative"
#                            )
#                        ),
#                        f"destination=global dict, CHUNKSIZE={chunksize}",
#                    )
#                    self.assertTrue(
#                        f6.equals(
#                            f4.regridc(
#                                dst, axes=("X", "Y"), method="conservative"
#                            )
#                        ),
#                        f"destination=global dict, CHUNKSIZE={chunksize}",
#                    )
#
#    @unittest.skipUnless(cf._found_ESMF, "Requires ESMF package.")
#    def test_Field_regrids_operator(self):
#        self.assertFalse(cf.regrid_logging())
#
#        with cf.atol(1e-12):
#            f1 = cf.read(self.filename1)[0]
#            f2 = cf.read(self.filename2)[0]
#            f3 = cf.read(self.filename3)[0]
#            f4 = cf.read(self.filename4)[0]
#            f5 = cf.read(self.filename5)[0]
#
#            op = f1.regrids(f2, "conservative", return_operator=True)
#            r = f1.regrids(op)
#            self.assertTrue(f3.equals(r))
#
#            # Repeat
#            r = f1.regrids(op)
#            self.assertTrue(f3.equals(r))
#
#            dst = {"longitude": f2.dim("X"), "latitude": f2.dim("Y")}
#            op = f1.regrids(
#                dst, "conservative", dst_cyclic=True, return_operator=True
#            )
#            r = f1.regrids(op)
#            self.assertTrue(f3.equals(r))
#
#            op = f1.regrids(
#                dst,
#                method="conservative",
#                dst_cyclic=True,
#                return_operator=True,
#            )
#            r = f1.regrids(op)
#            self.assertTrue(f3.equals(r))
#
#            # Regrid global to regional rotated pole
#            op = f1.regrids(f5, method="linear", return_operator=True)
#            r = f1.regrids(op)
#            self.assertTrue(f4.equals(r))
#
#        # Raise exception when the source grid does not match that of
#        # the regrid operator
#        op = f1.regrids(f2, "conservative", return_operator=True)
#        with self.assertRaises(ValueError):
#            f2.regrids(op)

#    @unittest.skipUnless(cf._found_ESMF, "Requires ESMF package.")
#    def test_Field_regridc_operator(self):
#        self.assertFalse(cf.regrid_logging())
#
#        with cf.atol(1e-12):
#            f1 = cf.read(self.filename7)[0]
#            f2 = cf.read(self.filename8)[0]
#            f3 = cf.read(self.filename9)[0]
#            f4 = cf.read(self.filename1)[0]
#            f5 = cf.read(self.filename2)[0]
#            f6 = cf.read(self.filename10)[0]
#
#            op = f1.regridc(
#                f2, axes="T", method="linear", return_operator=True
#            )
#            self.assertTrue(f3.equals(f1.regridc(op)))
#
#            op = f4.regridc(
#                f5,
#                axes=("X", "Y"),
#                method="conservative",
#                return_operator=True,
#            )
#            self.assertTrue(f6.equals(f4.regridc(op)))
#
#            op = f4.regridc(
#                f5,
#                axes=("X", "Y"),
#                method="conservative",
#                return_operator=True,
#            )
#            self.assertTrue(f6.equals(f4.regridc(op)))
#
#            dst = {
#                "X": f5.dimension_coordinate("X"),
#                "Y": f5.dimension_coordinate("Y"),
#            }
#            op = f4.regridc(
#                dst,
#                axes=("X", "Y"),
#                method="conservative",
#                return_operator=True,
#            )
#
#            self.assertTrue(f6.equals(f4.regridc(op)))
#            self.assertTrue(f6.equals(f4.regridc(op)))
#
#        # Raise exception when the source grid does not match that of
#        # the regrid operator
#        op = f1.regridc(f2, axes="T", method="linear", return_operator=True)
#        with self.assertRaises(ValueError):
#            f2.regrids(op)
#
#    @unittest.skipUnless(cf._found_ESMF, "Requires ESMF package.")
#    def test_Field_regrid_size1_dimensions(self):
#        # Check that non-regridded size 1 axes are handled OK
#        self.assertFalse(cf.regrid_logging())
#
#        f = cf.example_field(0)
#        shape = f.shape
#
#        g = f.regrids(f, method="linear")
#        self.assertEqual(g.shape, (shape))
#        g = f.regridc(f, method="linear", axes="X")
#        self.assertEqual(g.shape, (shape))
#
#        f.insert_dimension("T", position=0, inplace=True)
#        shape = f.shape
#        g = f.regrids(f, method="linear")
#        self.assertEqual(g.shape, shape)
#        g = f.regridc(f, method="linear", axes="X")
#        self.assertEqual(g.shape, shape)


if __name__ == "__main__":
    print("Run date:", datetime.datetime.now())
    cf.environment()
    print("")
    unittest.main(verbosity=2)

/*
** git $Id$
*******************************************************************************
** Copyright (c) 2002-2024 The ROMS/TOMS Group                               **
**   Licensed under a MIT/X style license                                    **
**   See License_ROMS.md                                                     **
*******************************************************************************
**
** Options for Gulf of Guinea model for COESSING Summer School
**
** Application flag:   GULFOFGUINEA
** Input script:       roms_gulfofguinea.in
*/

/* basic physics options */
#define SOLVE3D
#define UV_ADV
#define UV_COR
#define UV_QDRAG
#define UV_VIS2
#define MIX_S_UV
#define SPLINES_VDIFF
#define SPLINES_VVISC
#define DJ_GRADPS
#undef  ATM_PRESS
#define TS_DIF2
#define MIX_GEO_TS
#define CURVGRID
#define MASKING
#define SALINITY
#define NONLIN_EOS

/* outputs */
#define AVERAGES
#undef  DIAGNOSTICS_TS
#undef  DIAGNOSTICS_UV
#undef  STATIONS
#undef  FLOATS
#define DEFLATE
#define HDF5

/* air-sea fluxes and vertical mixing */
#define ANA_BTFLUX
#define ANA_BSFLUX

#define BULK_FLUXES
#define GLS_MIXING

#ifdef BULK_FLUXES
# define CRAIG_BANNER
# define CHARNOK
# define WIND_MINUS_CURRENT
# define SOLAR_SOURCE
# define LONGWAVE_OUT
# undef  DIURNAL_SRFLUX
# define EMINUSP
#endif

#if defined GLS_MIXING
# undef  CANUTO_A
# define KANTHA_CLAYSON
# define N2S2_HORAVG
# define RI_SPLINES
#else
# define ANA_VMIX
#endif

/* open boundaries */
#define RADIATION_2D
#define SSH_TIDES       /* Tides will be introduced by hourly boundary zeta,ubar,vbar */
#define UV_TIDES
#define ADD_FSOBC       /* These do nothing if TIDES are not defined */
#define ADD_M2OBC
#define TIDE_GENERATING_FORCES
#undef  ANA_NUDGCOEF

/* biology */
#undef BIO_FENNEL
#ifdef BIO_FENNEL
# define ANA_BIOLOGY
# define ANA_SPFLUX
# define ANA_BPFLUX
#endif

/* passive tracers */
#undef T_PASSIVE
#ifdef T_PASSIVE
# define ANA_SPFLUX
# define ANA_BPFLUX
#endif





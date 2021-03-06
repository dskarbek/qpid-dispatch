#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

# Find libwebsockets include dirs and libraries.
#
# Sets the following variables:
#
#   LibWebSockets_FOUND            - True if headers and requested libraries were found
#   LibWebSockets_INCLUDE_DIRS     - LibWebSockets include directories
#   LibWebSockets_LIBRARIES        - Link these to use libwebsockets.
#
# This module reads hints about search locations from variables::
#   LIBWEBSOCKETS_LIBRARYDIR       - Preferred library directory e.g. <prefix>/lib
#   LIBWEBSOCKETS_ROOT             - Preferred installation prefix
#   CMAKE_INSTALL_PREFIX           - Install location for the current project.
#   LIBWEBSOCKETS_INCLUDEDIR       - Preferred include directory e.g. <prefix>/include

find_library(LibWebSockets_LIBRARIES
  NAMES websockets libwebsockets
  HINTS ${LIBWEBSOCKETS_LIBRARYDIR} ${LIBWEBSOCKETS_ROOT}  ${CMAKE_INSTALL_PREFIX}
  )

find_path(LibWebSockets_INCLUDE_DIRS
  NAMES libwebsockets.h
  HINTS ${LIBWEBSOCKETS_INCLUDEDIR} ${LIBWEBSOCKETS_ROOT}/include ${CMAKE_INSTALL_PREFIX}/include
  PATHS /usr/include
  )

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(LibWebSockets DEFAULT_MSG LibWebSockets_LIBRARIES LibWebSockets_INCLUDE_DIRS)

if(NOT LibWebSockets_FOUND)
  set(LibWebSockets_LIBRARIES "")
  set(LibWebSockets_INCLUDE_DIRS "")
endif()

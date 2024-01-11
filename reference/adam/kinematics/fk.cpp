#include "xarm_kinematics_interface.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
/* Test xArm6 FK and IK at the same time */
/* input: joint angles (dimension: DOF) in degree */

/* *************************************************/
/* execution example: ./main 10 -30 -25 100 0 -52  */
/* *************************************************/

int main(int argc, char **argv)
{
	double deg2rad = M_PI/180.0; // convert from degree to radian

	if(argc!=19){
	    fprintf(stderr, "argc not == 25(pose_rpy + tcp_offset + world_offset)\n" );
		exit(-1);
	}

	double theta[6]={0}, tcp_offset[6]={0}, world_offset[6]={0};

	for(int j=0;j<6;j++)
		theta[j] = std::atof(argv[j+1])*deg2rad;

	for(int j=0;j<6;j++)
		if (j<3) tcp_offset[j] = std::atof(argv[j+7]);
		else tcp_offset[j] = std::atof(argv[j+7])*deg2rad;

	for(int j=0;j<6;j++)
		if (j<3) world_offset[j] = std::atof(argv[j+13]);
		else world_offset[j] = std::atof(argv[j+13])*deg2rad;

	/* For xArm6 or 7, joint limits have to be passed, just use the Macros defined in 'xarm_kinematics_interface.h' */
	double q_min[6] = XARM6_ANGLE_MIN; // Use LIMITED joint range, strange solution may be avoided
	double q_max[6] = XARM6_ANGLE_MAX;
	double pose_rpy[6] = {0};

	// * Attention! MUST BE Configured before calling FK or IK !
	xarm6_config(q_max, q_min, tcp_offset, world_offset);


	/*** Method 2: Use [x,y,z,roll,pitch,yaw] as TCP expression */
	int ret = xarm6_forward_kinematics(theta, pose_rpy);
	if(ret)
	{
		fprintf(stderr, "\nIK (Pose) returns: %d, Solution Fail!\n", ret);
		exit(-1);
	}
	else
	{
		for(int i=0; i<3; i++)
	    {
		    fprintf(stderr, "%lf ", pose_rpy[i]);
	    }
		for(int i=0; i<3; i++)
	    {
		    fprintf(stderr, "%lf ", pose_rpy[i+3]/deg2rad);
	    }
	    fprintf(stderr, "\n");
	}
	return 0;
}
